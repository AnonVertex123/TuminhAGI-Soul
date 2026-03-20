"""
LEARNING LAYER V2 — Tự phản biện & Học có kiểm soát

Kiến trúc: RAG → Answer → Multi-layer Evaluator → Debate Engine → Truth Extractor
         → Memory V2 (weighted) → Policy Update

Features:
- 3 tầng Evaluator: grounding, consistency, semantic (chỉ học khi score ≥ 2)
- Debate Engine: A trả lời → B phản biện → A sửa (inject policy)
- Truth Extractor: rút fact không lưu nguyên câu
- Memory V2: facts (weight), errors (penalty)
- Policy Update: meta-learning (hallucination → avoid_unknown_book_names)
- Anti-drift: weight *= 0.97
- Fresh grounding: luôn re-check Wikipedia
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Paths & Constants
# ---------------------------------------------------------------------------

_MEMORY_V2_PATH = Path(__file__).resolve().parents[1] / "memory" / "learning_layer_v2.json"
_POLICY_PATH = Path(__file__).resolve().parents[1] / "memory" / "learning_policy.json"
EVAL_SCORE_THRESHOLD = 2  # Chỉ học khi score ≥ 2
WEIGHT_DELTA = 0.1
PENALTY_DELTA = 0.2
MEMORY_DECAY_V2 = 0.97
SOURCE_QUALITY_THRESHOLD = 100  # Min chars để học

DEFAULT_POLICY = {
    "always_check_context": True,
    "avoid_unknown_book_names": True,
    "hallucination_penalty_count": 0,
    "missing_context_count": 0,
    # Meta-learning: AI học cách học
    "reduce_creativity_on_hallucination": True,
    "increase_retrieval_on_missing_context": True,
}

ENTITY_STRIP = re.compile(
    r"\s+(là\s*ai\??|la\s*ai\??|là\s*gì\??|la\s*gi\??|ở\s*đâu\??|khi\s*nào\??|của\s*ai\??)\s*$",
    re.IGNORECASE,
)


def _get_entity_key(query: str, entities: list[str] | None = None) -> str:
    if entities and entities:
        return entities[0].strip()
    stripped = ENTITY_STRIP.sub("", (query or "").strip())
    return stripped[:80] if stripped else (query or "")[:80]


# ---------------------------------------------------------------------------
# 1. Multi-layer Evaluator (chống học sai)
# ---------------------------------------------------------------------------

def _grounded(answer: str, context: str) -> bool:
    """Có nằm trong context không?"""
    try:
        from tools.search_mandate import fact_check
        return fact_check(context, answer)
    except ImportError:
        ctx_lower = (context or "").lower()
        a_words = [w for w in (answer or "").split() if len(w) >= 2]
        if not a_words:
            return True
        in_ctx = sum(1 for w in a_words if w.lower() in ctx_lower)
        return in_ctx / len(a_words) >= 0.5


def _consistent(
    answer: str,
    question: str,
    call_llm: Callable[[str, str], str],
) -> bool:
    """
    Hỏi lại dạng khác — model trả lời tương tự không?
    Đơn giản: hỏi "Xác nhận: [answer] có đúng không?" và kiểm tra phản hồi.
    """
    try:
        prompt = f"Câu hỏi gốc: {question}\n\nTrả lời cần xác nhận: {answer}\n\nTrả lời 'đúng' hoặc 'sai' (chỉ 1 từ):"
        out = call_llm("validator", prompt, "").lower().strip()
        return "đúng" in out or "correct" in out or "yes" in out
    except Exception:
        return False


def _semantic_correct(
    answer: str,
    context: str,
    call_llm: Callable[[str, str], str],
) -> bool:
    """Model check logic — nội dung có hợp lý so với context?"""
    try:
        prompt = (
            f"CONTEXT:\n{context[:800]}\n\nANSWER:\n{answer}\n\n"
            "Câu trả lời có logic và khớp với context không? Trả lời 'đúng' hoặc 'sai' (chỉ 1 từ):"
        )
        out = call_llm("validator", prompt, "").lower().strip()
        return "đúng" in out or "correct" in out or "yes" in out
    except Exception:
        return False


def evaluate(
    answer: str,
    context: str,
    question: str = "",
    *,
    call_llm: Callable[[str, str, str], str] | None = None,
    skip_llm_checks: bool = True,  # False = full 3-layer (consistency + semantic)
) -> int:
    """
    3 tầng kiểm tra. Trả về score 0–3.
    Chỉ học khi score ≥ EVAL_SCORE_THRESHOLD (2).
    """
    score = 0
    if _grounded(answer, context):
        score += 1

    if not skip_llm_checks and call_llm and question:
        def _call(persona: str, msg: str, ctx: str) -> str:
            return call_llm(persona, msg, ctx)

        if _consistent(answer, question, _call):
            score += 1
        if _semantic_correct(answer, context, _call):
            score += 1
    else:
        # Fallback: nếu grounded thì coi như +1, thêm +1 nếu confidence cao
        try:
            from tools.search_mandate import confidence, CONFIDENCE_THRESHOLD
            if confidence(answer, context) >= CONFIDENCE_THRESHOLD * 1.5:
                score += 1
        except ImportError:
            pass
        if score >= 1:
            score = min(2, score + 1)  # Coi grounded + reasonable = 2

    return score


# ---------------------------------------------------------------------------
# 2. Debate Engine (A trả lời → B phản biện → A sửa)
# ---------------------------------------------------------------------------

def debate(
    answer: str,
    context: str,
    question: str,
    *,
    call_critic: Callable[[str, str], str],
    call_refine: Callable[[str, str], str],
    policy_block: str = "",
) -> str:
    """
    Model A → trả lời (answer)
    Model B (critic) → phản biện
    Model A (refine) → sửa lại — inject policy để tránh lỗi đã học
    """
    critique = call_critic(
        f"Câu hỏi: {question}\n\nTrả lời cần phản biện: {answer}",
        context,
    )
    policy_rules = (
        f"\n\n[POLICY — BẮT BUỘC]\n{policy_block}\n[/POLICY]\n"
        if policy_block.strip()
        else ""
    )
    refine_prompt = (
        f"Câu hỏi: {question}\n\nTrả lời ban đầu: {answer}\n\n"
        f"Phản biện: {critique}\n\n"
        f"Hãy sửa lại trả lời DỰA TRÊN context dưới đây, KHÔNG bịa."
        f"{policy_rules}\n"
        "Chỉ dùng thông tin có trong CONTEXT:"
    )
    refined = call_refine(refine_prompt, context)
    return refined.strip() or answer


# ---------------------------------------------------------------------------
# 3. Truth Extractor (rút fact, không lưu nguyên câu)
# ---------------------------------------------------------------------------

def extract_fact(
    context: str,
    *,
    call_llm: Callable[[str], str] | None = None,
    max_facts: int = 5,
) -> list[str]:
    """
    Trích fact từ context. VD: "Hải Thượng Lãn Ông = Lê Hữu Trác"
    """
    if call_llm:
        try:
            prompt = (
                f"Từ CONTEXT sau, trích tối đa {max_facts} fact dạng 'X = Y' hoặc 'X: Y' "
                "(chỉ sự thật, không giải thích):\n\n" + (context or "")[:1200]
            )
            out = call_llm(prompt).strip()
            lines = [s.strip() for s in out.replace(";", "\n").split("\n") if "=" in s or ":" in s]
            return [l for l in lines if len(l) >= 5][:max_facts]
        except Exception:
            pass

    # Fallback: câu có chứa "là", "=", dài vừa
    facts = []
    for sent in re.split(r"[.!?\n]+", context or ""):
        s = sent.strip()
        if 10 <= len(s) <= 150 and ("là" in s or "=" in s or ":" in s):
            facts.append(s)
    return facts[:max_facts]


# ---------------------------------------------------------------------------
# 4. Memory V2 (weighted)
# ---------------------------------------------------------------------------

def _load_memory_v2() -> dict[str, Any]:
    if _MEMORY_V2_PATH.exists():
        try:
            data = json.loads(_MEMORY_V2_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"entities": {}}
        except (json.JSONDecodeError, OSError):
            pass
    return {"entities": {}}


def _save_memory_v2(data: dict[str, Any]) -> None:
    _MEMORY_V2_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MEMORY_V2_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_memory_v2(
    entity: str,
    facts: list[str],
    score: int,
    *,
    wrong_answer: str | None = None,
) -> None:
    """
    Weighted learning. score ≥ 2: weight += 0.1
    score < 2: penalty += 0.2
    """
    data = _load_memory_v2()
    entities = data.setdefault("entities", {})
    if entity not in entities:
        entities[entity] = {"facts": [], "errors": []}

    ent = entities[entity]
    facts_list = ent.setdefault("facts", [])
    errors_list = ent.setdefault("errors", [])

    if score >= EVAL_SCORE_THRESHOLD:
        for f in facts:
            if not f.strip():
                continue
            existing = next((x for x in facts_list if x.get("text") == f), None)
            if existing:
                existing["weight"] = min(1.0, existing.get("weight", 0.5) + WEIGHT_DELTA)
            else:
                facts_list.append({"text": f.strip(), "weight": 0.5 + WEIGHT_DELTA})
    else:
        if wrong_answer and wrong_answer.strip():
            errors_list.append({"text": wrong_answer[:200], "penalty": PENALTY_DELTA})

    _save_memory_v2(data)


# ---------------------------------------------------------------------------
# 5. Policy Update
# ---------------------------------------------------------------------------

def _load_policy() -> dict[str, Any]:
    if _POLICY_PATH.exists():
        try:
            return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_POLICY.copy()


def _save_policy(p: dict[str, Any]) -> None:
    _POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _POLICY_PATH.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def update_policy(score: int, error_type: str = "") -> None:
    """
    Policy Update — thay đổi cách trả lời.
    Meta-learning: Nếu sai do hallucination → giảm creativity, avoid_unknown_book_names
                  Nếu sai do thiếu context → tăng retrieval, always_check_context
    """
    p = _load_policy()
    if score >= EVAL_SCORE_THRESHOLD:
        pass  # Giữ policy
    else:
        err = error_type.lower()
        if "hallucination" in err or "bịa" in err or "wrong" in err:
            p["avoid_unknown_book_names"] = True
            p["reduce_creativity_on_hallucination"] = True
            p["hallucination_penalty_count"] = p.get("hallucination_penalty_count", 0) + 1
        if "context" in err or "grounded" in err or "confidence" in err:
            p["always_check_context"] = True
            p["increase_retrieval_on_missing_context"] = True
            p["missing_context_count"] = p.get("missing_context_count", 0) + 1
    _save_policy(p)


def get_policy_block() -> str:
    """Inject policy vào prompt."""
    p = _load_policy()
    lines = []
    if p.get("always_check_context"):
        lines.append("- LUÔN kiểm tra mọi tuyên bố trong CONTEXT trước khi trả lời.")
    if p.get("avoid_unknown_book_names"):
        lines.append("- KHÔNG bịa tên sách/tác phẩm nếu không có trong context.")
    if p.get("reduce_creativity_on_hallucination"):
        lines.append("- Ưu tiên trích dẫn đúng từ context hơn suy đoán sáng tạo.")
    if p.get("increase_retrieval_on_missing_context"):
        lines.append("- Khi thiếu thông tin trong context → nói 'chưa tìm thấy' thay vì bịa.")
    if not lines:
        return ""
    return "[POLICY — HỌC TỪ LỖI TRƯỚC]\n" + "\n".join(lines) + "\n[/POLICY]\n\n"


def get_policy_text() -> str:
    """Chỉ nội dung policy (không có wrapper) — dùng cho debate inject."""
    p = _load_policy()
    lines = []
    if p.get("always_check_context"):
        lines.append("- Kiểm tra CONTEXT trước khi trả lời.")
    if p.get("avoid_unknown_book_names"):
        lines.append("- KHÔNG bịa tên sách.")
    return "\n".join(lines) if lines else ""


# ---------------------------------------------------------------------------
# 6. Anti-drift & Source Quality
# ---------------------------------------------------------------------------

def apply_memory_decay_v2() -> None:
    """weight *= 0.97"""
    data = _load_memory_v2()
    for ent in (data.get("entities") or {}).values():
        for f in ent.get("facts") or []:
            f["weight"] = max(0.1, (f.get("weight", 0.5) * MEMORY_DECAY_V2))
    _save_memory_v2(data)


def source_quality_ok(context: str) -> bool:
    """Không phải context nào cũng học."""
    return len((context or "").strip()) >= SOURCE_QUALITY_THRESHOLD


# ---------------------------------------------------------------------------
# 7. Retrieve V2 (weighted facts)
# ---------------------------------------------------------------------------

def retrieve_knowledge_v2(query: str, entities: list[str] | None = None) -> tuple[str | None, str]:
    """Trả về (context_từ_memory, entity). Facts có weight cao ưu tiên."""
    entity = _get_entity_key(query, entities)
    data = _load_memory_v2()
    ent = (data.get("entities") or {}).get(entity)
    if not ent:
        return None, entity
    facts = sorted(
        (f for f in (ent.get("facts") or []) if f.get("weight", 0) >= 0.3),
        key=lambda x: x.get("weight", 0),
        reverse=True,
    )
    if not facts:
        return None, entity
    return "\n".join(f["text"] for f in facts[:5]), entity


def filter_wrong_v2(answer: str, entity: str) -> str | None:
    """Anti-repeat — từ errors đã biết."""
    data = _load_memory_v2()
    ent = (data.get("entities") or {}).get(entity)
    if not ent:
        return None
    ans = answer or ""
    for err in ent.get("errors") or []:
        t = err.get("text", "")
        if t and t in ans:
            return f"❌ known wrong: «{t}»"
    return None


# ---------------------------------------------------------------------------
# 8. Full Pipeline V2
# ---------------------------------------------------------------------------

def learning_v2(
    question: str,
    context: str,
    answer: str,
    *,
    entities: list[str] | None = None,
    call_llm: Callable[[str, str, str], str] | None = None,
    call_critic: Callable[[str, str], str] | None = None,
    call_refine: Callable[[str, str], str] | None = None,
    full_evaluate: bool = False,  # True = 3-layer (consistency + semantic)
) -> tuple[str, bool]:
    """
    Full Learning V2 Pipeline.
    Trả về (final_answer, was_updated).
    """
    entity = _get_entity_key(question, entities)
    if not source_quality_ok(context):
        return answer, False

    skip_llm = not full_evaluate
    score = evaluate(answer, context, question, call_llm=call_llm, skip_llm_checks=skip_llm)

    if score < EVAL_SCORE_THRESHOLD and call_critic and call_refine:
        try:
            policy_block = get_policy_text()
            refined = debate(
                answer, context, question,
                call_critic=call_critic,
                call_refine=call_refine,
                policy_block=policy_block,
            )
            score = evaluate(refined, context, question, call_llm=call_llm, skip_llm_checks=skip_llm)
            if score >= EVAL_SCORE_THRESHOLD:
                answer = refined
            else:
                update_policy(score, "low_score_after_debate")
        except Exception:
            pass

    facts = []
    if call_llm:
        try:
            facts = extract_fact(context, call_llm=lambda p: call_llm("task", p, context))
        except Exception:
            pass
    if not facts:
        facts = extract_fact(context)
    if not facts:
        facts = [context[:300]] if context else []

    update_memory_v2(
        entity,
        facts,
        score,
        wrong_answer=answer if score < EVAL_SCORE_THRESHOLD else None,
    )
    update_policy(score, "low_grounding" if score < EVAL_SCORE_THRESHOLD else "")

    return answer, score >= EVAL_SCORE_THRESHOLD


__all__ = [
    "evaluate",
    "debate",
    "get_policy_text",
    "extract_fact",
    "update_memory_v2",
    "update_policy",
    "get_policy_block",
    "retrieve_knowledge_v2",
    "filter_wrong_v2",
    "apply_memory_decay_v2",
    "source_quality_ok",
    "learning_v2",
    "_get_entity_key",
    "EVAL_SCORE_THRESHOLD",
]
