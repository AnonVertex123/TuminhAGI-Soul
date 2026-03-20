"""
LEARNING LAYER — Trí nhớ lõi TuminhAGI

Kiến trúc: User Query → RAG → Answer → Evaluator → Learning Layer → Memory Update
Learning = Memory + Feedback + Update
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Memory System (trí nhớ lõi)
# ---------------------------------------------------------------------------

MEMORY_PATH = Path(__file__).resolve().parents[1] / "memory" / "learning_layer.json"
MEMORY_DECAY_FACTOR = 0.95
REINFORCE_CORRECT = 0.05
REINFORCE_WRONG = -0.1

DEFAULT_MEMORY: dict[str, Any] = {
    "entities": {},
    "skills": {},
}

# Pattern lấy entity từ câu hỏi (fallback khi không có extract_wiki_entities)
ENTITY_STRIP = re.compile(
    r"\s+(là\s*ai\??|la\s*ai\??|là\s*gì\??|la\s*gi\??|ở\s*đâu\??|khi\s*nào\??|của\s*ai\??)\s*$",
    re.IGNORECASE,
)


def _load_memory() -> dict[str, Any]:
    if MEMORY_PATH.exists():
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else DEFAULT_MEMORY.copy()
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_MEMORY.copy()


def _save_memory(data: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_entity_key(query: str, entities: list[str] | None = None) -> str:
    """Lấy entity chính từ query hoặc danh sách entities."""
    if entities and entities:
        return entities[0].strip()
    stripped = ENTITY_STRIP.sub("", (query or "").strip())
    return stripped[:80] if stripped else (query or "")[:80]


# ---------------------------------------------------------------------------
# Error Detection (phát hiện sai)
# ---------------------------------------------------------------------------

def detect_error(answer: str, context: str, *, wrong_facts: list[str] | None = None) -> tuple[bool, str | None]:
    """
    Rule-based error detection.
    Trả về (has_error, wrong_phrase).
    """
    ans = answer or ""
    wrong_list = wrong_facts or []

    # 1. Known wrong facts (từ memory)
    for wrong in wrong_list:
        if wrong and wrong in ans:
            return True, wrong

    # 2. HALLUCINATION_PATTERNS
    try:
        from tools.search_mandate import HALLUCINATION_PATTERNS
        for phrase in HALLUCINATION_PATTERNS:
            if phrase in ans:
                return True, phrase
    except ImportError:
        if "Bản thảo sức khỏe" in ans:
            return True, "Bản thảo sức khỏe"

    # 3. Context mismatch
    try:
        from tools.search_mandate import fact_check
        if not fact_check(context, answer):
            return True, "context_mismatch"
    except ImportError:
        pass

    return False, None


# ---------------------------------------------------------------------------
# Correction Engine (lấy sự thật từ context)
# ---------------------------------------------------------------------------

def extract_truth(context: str, *, max_chars: int = 500) -> str:
    """Đơn giản: lấy đoạn đầu context chứa fact chính."""
    ctx = (context or "").strip()
    return ctx[:max_chars] if ctx else ""


# ---------------------------------------------------------------------------
# Memory Update
# ---------------------------------------------------------------------------

def update_memory(
    entity: str,
    correct: str | None = None,
    wrong: str | None = None,
    *,
    is_correct: bool | None = None,
) -> None:
    """
    Cập nhật memory cho entity.
    correct: fact đúng (từ context)
    wrong: fact sai (từ answer bị reject)
    is_correct: reinforcement — True thì +0.05 confidence, False thì -0.1
    """
    data = _load_memory()
    entities = data.setdefault("entities", {})

    if entity not in entities:
        entities[entity] = {
            "correct_facts": [],
            "wrong_facts": [],
            "confidence": 0.5,
        }

    ent = entities[entity]
    if correct and correct.strip() and correct not in ent["correct_facts"]:
        ent["correct_facts"].append(correct.strip())
    if wrong and wrong.strip() and wrong not in ent["wrong_facts"]:
        ent["wrong_facts"].append(wrong.strip())

    if is_correct is True:
        ent["confidence"] = min(1.0, ent.get("confidence", 0.5) + REINFORCE_CORRECT)
    elif is_correct is False:
        ent["confidence"] = max(0.0, ent.get("confidence", 0.5) + REINFORCE_WRONG)

    _save_memory(data)


# ---------------------------------------------------------------------------
# Retrieval ưu tiên memory
# ---------------------------------------------------------------------------

def retrieve_knowledge(query: str, entities: list[str] | None = None):
    """
    Lần sau hỏi lại: ưu tiên memory trước.
    Trả về (context_from_memory, entity_key) hoặc (None, entity_key).
    """
    entity = _get_entity_key(query, entities)
    data = _load_memory()
    ent = (data.get("entities") or {}).get(entity)
    if not ent:
        return None, entity
    correct = ent.get("correct_facts") or []
    if not correct:
        return None, entity
    return "\n\n".join(correct), entity


# ---------------------------------------------------------------------------
# Anti-repeat error (cực quan trọng)
# ---------------------------------------------------------------------------

def filter_wrong(answer: str, entity: str) -> str | None:
    """
    Nếu answer chứa wrong_fact đã biết → trả về reason reject.
    """
    data = _load_memory()
    ent = (data.get("entities") or {}).get(entity)
    if not ent:
        return None
    wrong_list = ent.get("wrong_facts") or []
    ans = answer or ""
    for wrong in wrong_list:
        if wrong and wrong in ans:
            return f"❌ known wrong fact: «{wrong}»"
    return None


# ---------------------------------------------------------------------------
# Memory decay (tránh overfit sai)
# ---------------------------------------------------------------------------

def apply_memory_decay() -> None:
    """Giảm confidence nhẹ để tránh overfit."""
    data = _load_memory()
    for ent in (data.get("entities") or {}).values():
        c = ent.get("confidence", 0.5)
        ent["confidence"] = max(0.0, c * MEMORY_DECAY_FACTOR)
    _save_memory(data)


# ---------------------------------------------------------------------------
# Learning Trigger & Pipeline
# ---------------------------------------------------------------------------

def trigger_learning(
    question: str,
    answer: str,
    context: str,
    *,
    entities: list[str] | None = None,
    reason: str = "",
) -> bool:
    """
    Hệ chỉ học khi answer_wrong hoặc low_confidence.
    Gọi sau khi grounded_reject_check failed.
    Trả về True nếu đã cập nhật memory.
    """
    entity = _get_entity_key(question, entities)
    data = _load_memory()
    ent = (data.get("entities") or {}).get(entity)
    wrong_facts = (ent.get("wrong_facts") or []) if ent else []

    has_err, wrong_phrase = detect_error(answer, context, wrong_facts=wrong_facts)
    if not has_err and "low confidence" not in reason.lower():
        return False

    correct = extract_truth(context)
    wrong = wrong_phrase if wrong_phrase and wrong_phrase != "context_mismatch" else answer[:200]
    update_memory(entity, correct=correct, wrong=wrong, is_correct=False)
    return True


def learning_pipeline(
    question: str,
    context: str,
    generate_answer: Any,
    *,
    entities: list[str] | None = None,
) -> str:
    """
    Full Learning Loop:
    generate_answer(context) → detect_error → update_memory → return.
    """
    answer = generate_answer(context) if callable(generate_answer) else str(generate_answer)
    has_err, wrong_phrase = detect_error(answer, context)

    if has_err:
        entity = _get_entity_key(question, entities)
        correct = extract_truth(context)
        wrong = wrong_phrase if wrong_phrase != "context_mismatch" else answer[:200]
        update_memory(entity, correct=correct, wrong=wrong, is_correct=False)
        return "Corrected using learning"

    return answer


# ---------------------------------------------------------------------------
# Inject memory vào context (trước khi generate)
# ---------------------------------------------------------------------------

def inject_learned_context(
    base_context: str,
    query: str,
    entities: list[str] | None = None,
) -> tuple[str, str | None]:
    """
    Nếu có memory cho entity → prepend correct_facts vào context.
    Trả về (enhanced_context, entity_key).
    """
    mem_ctx, entity = retrieve_knowledge(query, entities)
    if not mem_ctx:
        return base_context, entity
    prefix = "[ĐÃ HỌC — ƯU TIÊN]\n" + mem_ctx + "\n\n[CONTEXT MỚI]\n"
    return prefix + base_context, entity


__all__ = [
    "MEMORY_PATH",
    "detect_error",
    "extract_truth",
    "update_memory",
    "retrieve_knowledge",
    "filter_wrong",
    "apply_memory_decay",
    "trigger_learning",
    "learning_pipeline",
    "inject_learned_context",
    "_get_entity_key",
]
