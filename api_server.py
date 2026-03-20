from __future__ import annotations

import asyncio
import json
import math
import queue
import os
import requests
import sys
import threading
from functools import lru_cache
from typing import Any, Dict, Generator, Optional

import numpy as np

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from missions_hub.medical_diagnostic_tool import MedicalDiagnosticTool, diagnose_enhanced
from nexus_core.eternal_memory import EternalMemoryManager
from nexus_core.professor_reasoning import ProfessorReasoning
from nexus_core.output_formatter import format_output as _format_output

app = FastAPI(title="Tự Minh AGI API Server")

app.add_middleware(
    CORSMiddleware,
    # Chỉ cho phép frontend Next.js chạy ở localhost:3000
    # (Nếu allow_credentials=True thì không thể dùng wildcard "*".)
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
        "http://localhost:3020",
        "http://127.0.0.1:3020",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_tool_lock = threading.Lock()
_tool_instance: Optional[MedicalDiagnosticTool] = None

_eternal_lock = threading.Lock()
_eternal_instance: Optional[EternalMemoryManager] = None


@app.on_event("startup")
async def _startup_warmup() -> None:
    """
    Pre-load the ICD vault + unit_vault when uvicorn starts.
    This pays the cold-start I/O cost once so every subsequent request
    hits a hot in-memory cache.  Runs in a thread to stay non-blocking.
    """
    def _load() -> None:
        try:
            tool = get_tool()
            if tool.df is None:
                tool.load_vault()
            # Pre-warm the Phase-1 LRU cache for the most common symptom clusters.
            _COMMON = [
                "sốt cao, cứng cổ",
                "tiểu buốt, tiểu giắt, nước tiểu đục",
                "ho kéo dài, khó thở",
                "đau bụng, buồn nôn",
                "đau ngực, hồi hộp",
                "đau đầu dữ dội, buồn nôn",
                "sốt cao, đau đầu, phát ban",
            ]
            for s in _COMMON:
                _suggest_questions_p1(s.lower())
            print("✅ [Warm-up] ICD vault loaded + LRU cache seeded.")
        except Exception as exc:
            print(f"⚠️  [Warm-up] Non-fatal error: {exc}")

    threading.Thread(target=_load, daemon=True, name="warmup").start()


def get_tool() -> MedicalDiagnosticTool:
    global _tool_instance
    with _tool_lock:
        if _tool_instance is None:
            _tool_instance = MedicalDiagnosticTool()
        return _tool_instance


def get_eternal() -> EternalMemoryManager:
    """Lazy-load EternalMemoryManager (vector DB)."""
    global _eternal_instance
    with _eternal_lock:
        if _eternal_instance is None:
            _eternal_instance = EternalMemoryManager()
        return _eternal_instance


def _sse(data: Dict[str, Any]) -> str:
    """
    Minimal SSE encoder. We always send one `data:` line per event.
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "routes": [
                "GET /diagnose/stream",
                "POST /diagnose",
                "POST /command"
            ],
        }
    )


def _classify_line(line: str) -> Optional[str]:
    """
    Map backend console lines to timeline steps used by frontend.
    """
    l = line.lower()

    # Critic
    if "khóa critic" in l:
        return "critic"
    if "đao phủ" in line.lower() or "critic" in l or "skeptic critic" in l:
        return "critic"

    # Reverse check
    if "reverse description check" in l or "reverse" in l and "mô tả" in line.lower():
        return "reverse"
    if "reverse check" in l or "đang chạy khóa" in l and "reverse" in l:
        return "reverse"

    # Chapter guard
    if "khóa chương" in line.lower() or "chapter guard" in l:
        return "chapter"

    # Final
    if "tổng kết" in l or "success" in l or "martial law" in l:
        return "final"

    return None


def _softmax(xs: list[float], temp: float = 1.0) -> list[float]:
    """Numerically stable softmax using numpy (vectorized, no loop-level imports)."""
    if not xs:
        return []
    arr = np.asarray(xs, dtype=np.float64)
    arr = (arr - arr.max()) / max(float(temp), 1e-9)
    e = np.exp(arr)
    return (e / e.sum()).tolist()


# ---------------------------------------------------------------------------
# Module-level keyword sets — built ONCE, reused on every call.
# Avoids recreating Python list literals inside hot paths.
# ---------------------------------------------------------------------------
_KW_FEVER = frozenset(["sốt cao", "sot cao", "high fever", "fever"])
_KW_NECK  = frozenset(["cứng cổ", "cung co", "neck stiffness", "stiff neck"])
_KW_RESP  = frozenset(["ho", "khò khè", "khó thở", "cough", "wheezing", "shortness of breath"])
_KW_URINE = frozenset(["tiểu buốt", "tiểu giắt", "tiểu rắt", "dysuria", "cloudy urine"])
_KW_CARD  = frozenset(["đau ngực", "hồi hộp", "chest pain", "palpitation"])
_KW_GI    = frozenset(["đau bụng", "nôn", "tiêu chảy", "abdominal pain", "vomiting", "diarrhea"])


def _suggest_questions(symptoms: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Heuristic follow-up questions for differential diagnosis.
    Phase 2: includes per-code weight multipliers when candidates are known.
    Can also be called with empty candidates for Phase 1 (early keyword-only emission).
    """
    text = (symptoms or "").lower()
    # Build code list once — reused across all effect dicts below.
    codes: list[str] = [str(c.get("code") or "") for c in candidates]

    qs: list[dict[str, Any]] = []

    def _effects(yes_w: float, no_w: float) -> dict[str, Any]:
        """Return effects dict.  O(|codes|) but only allocated when condition fires."""
        if codes:
            return {"yes": {c: yes_w for c in codes}, "no": {c: no_w for c in codes}}
        return {"yes": {}, "no": {}}

    def add(qid: str, label: str, yes_w: float, no_w: float) -> None:
        qs.append({"id": qid, "label": label, "effects": _effects(yes_w, no_w)})

    # Emergency / meningitis-like — check frozenset membership (O(1) per keyword)
    has_fever = any(k in text for k in _KW_FEVER)
    has_neck  = any(k in text for k in _KW_NECK)
    if has_fever and has_neck:
        add("kernig",      "Có dấu hiệu Kernig/Brudzinski (đau khi gập cổ/duỗi gối)?", 1.25, 0.85)
        add("photophobia", "Có sợ ánh sáng / đau đầu tăng khi nhìn sáng không?",        1.15, 0.92)
        add("vomit",       "Có nôn vọt / lơ mơ / tri giác thay đổi?",                   1.20, 0.90)

    # Respiratory
    if any(k in text for k in _KW_RESP):
        add("sputum", "Ho có đờm (xanh/vàng) hoặc sốt kèm đau ngực khi hít sâu?", 1.18, 0.93)

    # Urinary
    if any(k in text for k in _KW_URINE):
        add("flank_pain", "Có đau hông lưng, ớn lạnh, sốt cao (nghi viêm thận-bể thận)?", 1.20, 0.90)

    # Cardiovascular
    if any(k in text for k in _KW_CARD):
        add("exertion", "Triệu chứng tăng khi gắng sức / leo cầu thang?", 1.15, 0.88)

    # GI
    if any(k in text for k in _KW_GI):
        add("bloody_stool", "Có máu trong phân / nôn ra máu không?", 1.20, 0.90)

    # Always add a general discriminator
    add("duration", "Triệu chứng kéo dài > 7 ngày hoặc nặng dần?", 1.08, 0.97)

    return qs[:6]


@lru_cache(maxsize=2048)
def _suggest_questions_p1(symptoms_lower: str) -> list[dict[str, Any]]:
    """
    Phase-1 cached wrapper: pure keyword → questions with empty effects.
    lru_cache key = lowercased symptom string → O(1) on repeated queries.
    Called at SSE stream start before any Ollama I/O.
    """
    return _suggest_questions(symptoms_lower, [])


class QueueWriter:
    """
    Captures writes to stdout/stderr and pushes complete lines into a queue.
    """

    def __init__(self, q: queue.Queue[str]):
        self.q = q
        self._buf = ""

    def write(self, s: str) -> None:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip("\r").strip()
            if line:
                try:
                    self.q.put_nowait(line)
                except Exception:
                    pass

    def flush(self) -> None:
        # No-op for compatibility
        return


_stream_lock = threading.Lock()


@app.post("/diagnose")
def diagnose(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Non-streaming endpoint. Returns final diagnosis payload.
    """
    user_query = payload.get("query") or payload.get("symptoms") or payload.get("text")
    execution_mode = bool(payload.get("executionMode", False))

    if not user_query or not isinstance(user_query, str):
        raise HTTPException(status_code=400, detail="Missing/invalid `query` (string).")

    tool = get_tool()

    # Avoid polluting server console too much:
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    devnull_out = None
    devnull_err = None
    try:
        devnull_out = open(os.devnull, "w", encoding="utf-8", errors="ignore")
        devnull_err = open(os.devnull, "w", encoding="utf-8", errors="ignore")
        sys.stdout = devnull_out
        sys.stderr = devnull_err
    except Exception:
        pass

    try:
        result = tool.tuminh_multi_diagnostic_loop(user_query)
    finally:
        try:
            if devnull_out:
                devnull_out.close()
            if devnull_err:
                devnull_err.close()
        except Exception:
            pass
        sys.stdout, sys.stderr = orig_stdout, orig_stderr

    # result shape:
    # (user_query, status_label, combined_codes, combined_name, confidence, summary, details)
    (
        q,
        status_label,
        combined_codes,
        _combined_name,
        confidence,
        summary,
        details,
    ) = result

    return JSONResponse(
        {
            "query": q,
            "status": status_label,
            "codes": combined_codes,
            "confidence": confidence,
            "summary": summary,
            "details": details,
            "executionMode": execution_mode,
        }
    )


@app.get("/diagnose/stream")
async def diagnose_stream(
    query: str = Query(..., description="Vietnamese symptom text"),
    executionMode: bool = Query(False, alias="executionMode"),
) -> StreamingResponse:
    """
    Streaming endpoint for UI timeline updates.
    We stream captured stdout lines and classify them into timeline steps.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Missing `query`.")

    # Serialize stream requests because stdout redirection is global.
    if not _stream_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another /diagnose/stream is running.")

    q: queue.Queue[str] = queue.Queue()
    done = threading.Event()
    tool = get_tool()
    orig_stdout, orig_stderr = sys.stdout, sys.stderr

    def worker() -> None:
        # Redirect stdout/stderr to queue so we can stream it.
        sys.stdout = QueueWriter(q)  # type: ignore[assignment]
        sys.stderr = QueueWriter(q)  # type: ignore[assignment]
        try:
            # ---------------------------------------------------------------
            # PHASE 1: Emit keyword-based questions IMMEDIATELY (<1 ms).
            # Uses lru_cache on lowercased symptoms → O(1) on repeated queries.
            # No Ollama call needed — pure string matching on the raw query.
            # The frontend shows these to the doctor while the backend works.
            # Phase 2 (inside critic_layer_streamed) re-emits with per-code
            # effects once candidates are available.
            # ---------------------------------------------------------------
            try:
                early_qs = _suggest_questions_p1(query.lower())
                if early_qs:
                    q.put_nowait(
                        "__DIFF_QUESTIONS__"
                        + json.dumps(
                            {"symptoms": query, "questions": early_qs, "phase": 1},
                            ensure_ascii=False,
                        )
                    )
            except Exception:
                pass

            # Ensure Chapter step appears in the UI immediately.
            q.put_nowait("KHÓA CHƯƠNG bắt đầu (Chapter Guard)")

            # Monkeypatch critic_layer to emit token-by-token reasoning.
            orig_critic = getattr(tool, "critic_layer")

            def critic_layer_streamed(symptoms: str, top_candidates: Any) -> Any:
                # Always emit differential checklist based on top_candidates first.
                cands: list[dict[str, Any]] = []
                try:
                    if isinstance(top_candidates, list):
                        cands = [
                            {
                                "code": str(c.get("code") or ""),
                                "description": str(c.get("description") or ""),
                                "score": float(c.get("score") or 0.0),
                            }
                            for c in top_candidates[:5]
                            if str(c.get("code") or "").strip()
                        ]
                    probs = _softmax([c["score"] for c in cands], temp=0.35)
                    diff = [
                        {
                            "code": cands[i]["code"],
                            "description": cands[i]["description"],
                            "prob": round(float(probs[i]) * 100.0, 1),
                        }
                        for i in range(len(cands))
                    ]
                    q.put_nowait(
                        "__DIFF_UPDATE__"
                        + json.dumps(
                            {"symptoms": symptoms, "items": diff},
                            ensure_ascii=False,
                        )
                    )
                    q.put_nowait(
                        "__DIFF_QUESTIONS__"
                        + json.dumps(
                            {"symptoms": symptoms, "questions": _suggest_questions(symptoms, cands)},
                            ensure_ascii=False,
                        )
                    )

                    # ── Professor Reasoning (Clinical Reasoning Engine) ──────
                    # Runs < 2 ms (pure Python+NumPy, no Ollama).
                    # Emits red flags, pathognomonic boosts, exclusion questions.
                    base_probs_pct = [d["prob"] for d in diff]
                    insight = ProfessorReasoning.analyze(symptoms, cands, base_probs_pct)
                    q.put_nowait(
                        "__EXPERT_INSIGHTS__"
                        + json.dumps(insight.to_dict(), ensure_ascii=False)
                    )
                except Exception:
                    pass

                try:
                    q.put_nowait("__CRITIC_START__")
                    critic_res = orig_critic(symptoms, top_candidates)
                    # Emit critic meta so frontend can color badges immediately.
                    meta: Dict[str, Any] = {}
                    if isinstance(critic_res, dict):
                        meta["status"] = critic_res.get("status")
                        meta["confidence"] = critic_res.get("confidence_score")
                        meta["best_candidate_index"] = critic_res.get("best_candidate_index")
                    q.put_nowait("__CRITIC_META__" + json.dumps(meta, ensure_ascii=False))

                    reasoning = ""
                    if isinstance(critic_res, dict):
                        reasoning = critic_res.get("reasoning") or ""
                    else:
                        reasoning = str(critic_res)

                    # Stream reasoning as characters.
                    # We do not delay here; frontend handles typewriter pacing.
                    for ch in reasoning:
                        q.put_nowait("__CRITIC_TOKEN__" + json.dumps(ch, ensure_ascii=False))
                    q.put_nowait("__CRITIC_END__")
                    return critic_res
                except Exception as e:
                    # Still return a safe result so pipeline continues.
                    q.put_nowait("__CRITIC_START__")
                    q.put_nowait(
                        "__CRITIC_META__"
                        + json.dumps({"status": "REJECTED", "confidence": 0, "best_candidate_index": "REJECT_ALL"}, ensure_ascii=False)
                    )
                    q.put_nowait(
                        "__CRITIC_TOKEN__"
                        + json.dumps(f"[Critic error: {e}]", ensure_ascii=False)
                    )
                    q.put_nowait("__CRITIC_END__")
                    # Minimal fallback
                    return {"best_candidate_index": "REJECT_ALL", "reasoning": "", "coverage_score": 0, "status": "REJECTED"}

            # Replace the bound method on this tool instance.
            setattr(tool, "critic_layer", critic_layer_streamed)

            res = tool.tuminh_multi_diagnostic_loop(query)
            # Put a final marker + result payload.
            q.put_nowait("__FINAL_RESULT__")
            q.put_nowait(json.dumps({"result": res}, ensure_ascii=False))
        except Exception as e:
            q.put_nowait("__ERROR__")
            q.put_nowait(json.dumps({"error": str(e)}, ensure_ascii=False))
        finally:
            done.set()

    # Start worker thread
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    async def event_gen() -> Generator[str, None, None]:
        try:
            # Stream while worker runs (or queue drains).
            while not done.is_set() or not q.empty():
                try:
                    line = q.get(timeout=0.1)
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue

                if line == "__FINAL_RESULT__":
                    # Next queue item should be the JSON result
                    try:
                        payload_line = q.get(timeout=1.0)
                    except queue.Empty:
                        payload_line = "{}"
                    data = json.loads(payload_line).get("result")
                    (
                        q0,
                        status_label,
                        combined_codes,
                        _combined_name,
                        confidence,
                        summary,
                        details,
                    ) = data

                    yield _sse(
                        {
                            "event": "final",
                            "payload": {
                                "query": q0,
                                "status": status_label,
                                "codes": combined_codes,
                                "confidence": confidence,
                                "summary": summary,
                                "details": details,
                                "executionMode": bool(executionMode),
                            },
                        }
                    )

                    # ── Output Layer V2.0: structured 4-section output ────────
                    # Build a safe, descriptive output from the raw diagnosis data.
                    # Reconstructs a lightweight diagnoses list from available fields.
                    try:
                        _diag_entries: list[dict] = []
                        for _code_str in (combined_codes or "").split(","):
                            _code_str = _code_str.strip()
                            if _code_str and _code_str != "NONE":
                                _diag_entries.append({
                                    "code":             _code_str,
                                    "name":             _code_str,   # description filled below
                                    "score":            confidence,
                                    "critic_status":    status_label,
                                    "critic_confidence": int(confidence * 100) if confidence else None,
                                    "reasoning":        details,
                                })
                        _is_em = status_label in ("EMERGENCY_WARN",)
                        _structured = _format_output(
                            query=q0,
                            diagnoses=_diag_entries,
                            parts=(q0 or "").replace("，", ",").split(","),
                            is_emergency=_is_em,
                            status_label=status_label,
                        )
                        yield _sse({
                            "event":   "structured_output",
                            "payload": _structured.to_dict(),
                        })
                    except Exception as _fmt_err:
                        yield _sse({"event": "structured_output_error",
                                    "payload": {"error": str(_fmt_err)}})
                    continue

                if line == "__ERROR__":
                    try:
                        payload_line = q.get(timeout=1.0)
                    except queue.Empty:
                        payload_line = "{}"
                    data = json.loads(payload_line)
                    yield _sse({"event": "error", "payload": data})
                    continue

                if line == "__CRITIC_START__":
                    yield _sse({"event": "critic_start"})
                    continue

                if line.startswith("__CRITIC_META__"):
                    meta_json = line[len("__CRITIC_META__") :]
                    try:
                        meta = json.loads(meta_json)
                    except Exception:
                        meta = {"raw": meta_json}
                    yield _sse({"event": "critic_meta", "payload": meta})
                    continue

                if line.startswith("__DIFF_UPDATE__"):
                    payload_json = line[len("__DIFF_UPDATE__") :]
                    try:
                        payload = json.loads(payload_json)
                    except Exception:
                        payload = {"raw": payload_json}
                    yield _sse({"event": "diff_update", "payload": payload})
                    continue

                if line.startswith("__DIFF_QUESTIONS__"):
                    payload_json = line[len("__DIFF_QUESTIONS__") :]
                    try:
                        payload = json.loads(payload_json)
                    except Exception:
                        payload = {"raw": payload_json}
                    yield _sse({"event": "diff_questions", "payload": payload})
                    continue

                if line.startswith("__EXPERT_INSIGHTS__"):
                    payload_json = line[len("__EXPERT_INSIGHTS__") :]
                    try:
                        payload = json.loads(payload_json)
                    except Exception:
                        payload = {"raw": payload_json}
                    yield _sse({"event": "expert_insights", "payload": payload})
                    continue

                if line == "__CRITIC_END__":
                    yield _sse({"event": "critic_end"})
                    continue

                if line.startswith("__CRITIC_TOKEN__"):
                    token_json = line[len("__CRITIC_TOKEN__") :]
                    try:
                        token = json.loads(token_json)
                    except Exception:
                        token = token_json
                    yield _sse({"event": "critic_token", "payload": {"token": token}})
                    continue

                step = _classify_line(line)
                if step:
                    yield _sse(
                        {
                            "event": "timeline_log",
                            "step": step,
                            "message": line,
                        }
                    )

            # Done
            yield _sse({"event": "done"})
        finally:
            # Restore stdout/stderr after streaming concludes
            sys.stdout = orig_stdout  # type: ignore[assignment]
            sys.stderr = orig_stderr  # type: ignore[assignment]
            _stream_lock.release()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/diagnose/v2")
async def diagnose_v2(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    V9.3 Enhanced Diagnostic — non-streaming JSON endpoint.

    Request body:
        {
            "symptoms": ["đau ngực trái", "khó thở"],
            "context": {
                "trigger": "gắng sức",
                "age": 68,
                "sex": "nam",
                "duration": "30 phút",
                "severity": "nặng"
            }
        }

    Response:
        {
            "is_emergency": true,
            "emergency_reason": "...",
            "embed_model": "...",
            "latency_ms": 45.2,
            "candidates": [
                {"disease_id": "I21", "name_vn": "Nhồi máu cơ tim cấp",
                 "score": 0.87, "urgency": "emergency", ...},
                ...
            ]
        }

    Uses EnhancedDiagnosticPipeline (3-layer: Enricher → Embedder → SeverityScorer).
    Falls back gracefully if pipeline unavailable.
    """
    symptoms: list[str] = payload.get("symptoms") or []
    context: dict[str, Any] = payload.get("context") or {}

    if not symptoms or not isinstance(symptoms, list):
        raise HTTPException(
            status_code=422,
            detail="Field `symptoms` must be a non-empty list of strings.",
        )

    symptoms = [str(s).strip() for s in symptoms if str(s).strip()]
    if not symptoms:
        raise HTTPException(status_code=422, detail="All symptoms were empty after stripping.")

    try:
        result = await diagnose_enhanced(symptoms, context)
        return JSONResponse(content=result)
    except RuntimeError as e:
        # EnhancedDiagnosticPipeline unavailable — surface clear error
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")


@app.post("/command")
def command(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Generic command endpoint used by the frontend overlay.
    It’s a lightweight bridge: the real actions can be wired later.
    """
    cmd_type = payload.get("type")
    if not cmd_type:
        raise HTTPException(status_code=400, detail="Missing `type` in payload.")
    return JSONResponse({"ok": True, "type": cmd_type, "payload": payload.get("payload")})


@app.post("/copilot/chat")
def copilot_chat(payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
    """
    Copilot mini-chat endpoint.
    Streams assistant response token-by-token over SSE (text/event-stream).
    """
    message = payload.get("message") or payload.get("query")
    context = payload.get("context") or {}

    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="Missing `message`.")

    tool = get_tool()
    ollama_gen_url = tool.ollama_gen_url
    model_name = getattr(tool, "summary_model", "llama3:8b")

    # Build vector DB retrieval context (ICD + Thuốc Nam notes).
    diagnosis_query = ""
    try:
        query = str(context.get("query") or "").strip()
        status = str(context.get("status") or "").strip()
        codes = str(context.get("codes") or "").strip()
        summary = str(context.get("summary") or "").strip()
        critic = str(context.get("criticReasoning") or "").strip()

        diagnosis_query = (
            f"ICD codes: {codes}\n"
            f"Status: {status}\n"
            f"Symptoms/query: {query}\n"
            f"Diagnosis summary: {summary}\n"
            f"Critic reasoning: {critic}\n"
            f"User question: {message}\n"
            f"[thuốc Nam] [ICD-10]"
        )
    except Exception:
        diagnosis_query = f"User question: {message}\n[thuốc Nam] [ICD-10]"

    try:
        eternal = get_eternal()
        memories = eternal.retrieve_memory(diagnosis_query, k=6) or []
        notes_text = "\n\n".join(
            [
                f"[score={m.get('score')}] {str(m.get('content') or '')}"
                for m in memories[:6]
                if str(m.get("content") or "").strip()
            ]
        )
    except Exception as e:
        notes_text = f"(Vector DB unavailable: {e})"

    # Prompt: explicitly includes diagnosis + critic reasoning for "why critic rejected".
    prompt = f"""
Bạn là Medical Copilot của Tự Minh AGI.
Yêu cầu: trả lời bằng tiếng Việt, chuyên nghiệp, có cấu trúc, và luôn ưu tiên an toàn.

=== DIAGNOSTIC CONTEXT (từ hệ thống hiện tại) ===
User symptoms/query: {context.get('query') or ''}
Current status: {context.get('status') or ''}
ICD codes: {context.get('codes') or ''}
Diagnosis summary: {context.get('summary') or ''}
Diagnosis details:
{context.get('details') or ''}
Critic reasoning (Đao phủ): 
{context.get('criticReasoning') or ''}

=== VECTOR DB NOTES (thuốc Nam + ICD) ===
{notes_text}

=== USER QUESTION ===
{message}

=== TASK ===
1) Nếu câu hỏi có ý: "Tại sao Đao phủ lại từ chối / giảm confidence", hãy phân tích rõ theo critic reasoning:
   - Điểm chưa khớp
   - Gợi ý hướng đi
   - Mã ICD thay thế (nếu có)
2) Nếu nghi ngờ cấp cứu (ví dụ sốt cao + cứng cổ), hãy đề xuất các kiểm tra lâm sàng liên quan (ví dụ Kernig/Brudzinski) và nhấn mạnh cần đi khám sớm.
3) Nếu câu hỏi hỏi về thuốc Nam/thuốc liên quan, chỉ gợi ý ở mức thông tin tổng quan dựa trên notes; KHÔNG tự ý kê đơn.

=== OUTPUT FORMAT (BẮT BUỘC) ===
1. Chẩn đoán hiện tại (tóm tắt)
2. Tại sao Đao phủ phản biện (dẫn từ critic reasoning)
3. Gợi ý hướng đi cho bác sĩ (các bước hỏi/khám/đi xét nghiệm liên quan)
4. Thuốc Nam / ICD liên quan (nếu phù hợp)
5. Lưu ý an toàn
"""

    q: queue.Queue[str] = queue.Queue()
    done = threading.Event()

    def worker() -> None:
        try:
            q.put_nowait("__COPILOT_START__")

            with requests.post(
                ollama_gen_url,
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": True,
                    "options": {"temperature": 0.2},
                },
                stream=True,
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    # Ollama streams JSON objects line-by-line.
                    try:
                        obj = json.loads(raw)
                    except Exception:
                        continue

                    # Common keys: "response" and "done".
                    chunk = obj.get("response") or ""
                    done_flag = bool(obj.get("done"))

                    if chunk:
                        for ch in str(chunk):
                            q.put_nowait("__COPILOT_TOKEN__" + json.dumps(ch, ensure_ascii=False))

                    if done_flag:
                        break

            q.put_nowait("__COPILOT_END__")
        except Exception as e:
            # Stream error as typewriter tokens for consistent UI behavior.
            err = str(e)
            for ch in err:
                q.put_nowait("__COPILOT_TOKEN__" + json.dumps(ch, ensure_ascii=False))
            q.put_nowait("__COPILOT_END__")
        finally:
            done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    async def event_gen() -> Generator[str, None, None]:
        try:
            while not done.is_set() or not q.empty():
                try:
                    line = q.get(timeout=0.1)
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue

                if line == "__COPILOT_START__":
                    # Client doesn't need meta right now, but keep for symmetry.
                    continue
                if line == "__COPILOT_END__":
                    yield _sse({"event": "copilot_end"})
                    continue
                if line.startswith("__COPILOT_ERROR__"):
                    err_json = line[len("__COPILOT_ERROR__") :]
                    try:
                        err = json.loads(err_json)
                    except Exception:
                        err = {"error": err_json}
                    yield _sse({"event": "copilot_error", "payload": err})
                    continue
                if line.startswith("__COPILOT_TOKEN__"):
                    token_json = line[len("__COPILOT_TOKEN__") :]
                    try:
                        token = json.loads(token_json)
                    except Exception:
                        token = token_json
                    yield _sse({"event": "copilot_token", "payload": {"token": token}})
                    continue
        finally:
            # nothing
            pass

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Federated Knowledge API (Medical module ONLY)
# ---------------------------------------------------------------------------

_federation_server = None


def _get_federation():
    global _federation_server
    if _federation_server is None:
        from pathlib import Path
        from missions_hub.knowledge_federation import FederationServer, KnowledgeContribution, ContributionType
        _federation_server = FederationServer(Path("data/knowledge_base.jsonl"))
    return _federation_server


@app.post("/api/knowledge/contribute")
async def knowledge_contribute(payload: Dict[str, Any] = Body(...)) -> JSONResponse:
    """
    Receive voluntary knowledge contribution. Auth: user token required (placeholder).
    """
    import uuid
    from missions_hub.knowledge_federation import (
        KnowledgeContribution,
        ContributionType,
    )
    try:
        ctype = payload.get("type", "treatment_outcome")
        try:
            ct = ContributionType(ctype)
        except ValueError:
            ct = ContributionType.TREATMENT_OUTCOME
        content = payload.get("content") or {}
        metadata = payload.get("metadata") or {}
        privacy = payload.get("privacy") or {}
        validation = payload.get("validation") or {}
        c = KnowledgeContribution(
            contribution_id=str(uuid.uuid4()),
            type=ct,
            content=content,
            metadata=metadata,
            privacy={
                "is_anonymous": True,
                "no_personal_info": True,
                "consent_given": bool(privacy.get("consent_given")),
            },
            validation={
                "evidence_level": validation.get("evidence_level", "self_reported"),
                "source": validation.get("source", "tự báo cáo"),
                "verified_by_md": bool(validation.get("verified_by_md", False)),
            },
        )
        server = _get_federation()
        result = await server.receive_contribution(c)
        return JSONResponse({
            "accepted": result.accepted,
            "contribution_id": c.contribution_id,
            "reason": result.reason,
        })
    except Exception as e:
        return JSONResponse(
            {"accepted": False, "reason": str(e), "contribution_id": ""},
            status_code=500,
        )


@app.get("/api/knowledge/stats")
def knowledge_stats() -> JSONResponse:
    """Public stats — no auth."""
    from pathlib import Path
    from datetime import datetime
    kb = Path("data/knowledge_base.jsonl")
    total = 0
    verified = 0
    regions: set[str] = set()
    last_updated = None
    if kb.exists():
        try:
            for line in kb.open(encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    obj = json.loads(line)
                    m = obj.get("metadata") or {}
                    if m.get("region"):
                        regions.add(str(m["region"]))
                    if obj.get("confidence", 0) >= 0.8:
                        verified += 1
                    ts = obj.get("updated_at") or obj.get("created_at")
                    if ts:
                        last_updated = ts
                except Exception:
                    pass
        except Exception:
            pass
    return JSONResponse({
        "total_contributions": total,
        "verified_entries": verified,
        "regions_covered": len(regions),
        "last_updated": last_updated,
    })


@app.get("/api/knowledge/changelog")
def knowledge_changelog(limit: int = Query(20, ge=1, le=100)) -> JSONResponse:
    """Recent knowledge updates (community changelog)."""
    from pathlib import Path
    kb = Path("data/knowledge_base.jsonl")
    entries: list[dict] = []
    if kb.exists():
        try:
            lines = kb.open(encoding="utf-8").readlines()
            for line in reversed(lines[-limit * 2:]):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    entries.append({
                        "type": obj.get("type", ""),
                        "updated_at": obj.get("updated_at", obj.get("created_at", "")),
                        "metadata": obj.get("metadata", {}),
                    })
                    if len(entries) >= limit:
                        break
                except Exception:
                    pass
        except Exception:
            pass
    return JSONResponse(entries)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

