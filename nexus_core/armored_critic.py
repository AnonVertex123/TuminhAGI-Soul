"""
nexus_core/armored_critic.py — Skeptic Critic "Bọc Thép"
=========================================================
Triple-Layer Parsing: đảm bảo critic_layer LUÔN trả về dict hợp lệ,
không bao giờ None, không bao giờ crash caller.

Schema thực tế của Tự Minh Critic:
{
    "best_candidate_index": 1 | 2 | 3 | "REJECT_ALL",
    "confidence_score":     0..100,
    "status":               "APPROVED" | "SUGGESTION" | "REJECTED",
    "reasoning":            "Điểm chưa khớp: ...\nGợi ý: ...\nMã ICD: ..."
}
"""
from __future__ import annotations

import json
import re
from typing import Any


# ── Default safe result (Layer 3 fallback) ───────────────────────────────────
_SAFE_FALLBACK: dict[str, Any] = {
    "best_candidate_index": 1,
    "confidence_score": 50.0,
    "status": "SUGGESTION",
    "reasoning": (
        "Điểm chưa khớp: Critic engine gặp lỗi định dạng — không phân tích được.\n"
        "Gợi ý hướng đi: Kết quả chỉ mang tính tham khảo, bác sĩ cần tự xác nhận.\n"
        "Mã ICD thay thế: (fallback — chưa xác định)"
    ),
}


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Chuẩn hóa dict sau khi parse thành công — đảm bảo đúng schema và kiểu dữ liệu.
    """
    # best_candidate_index: int 1-3 hoặc chuỗi "REJECT_ALL"
    bci = raw.get("best_candidate_index", 1)
    if isinstance(bci, str) and bci.upper() == "REJECT_ALL":
        raw["best_candidate_index"] = "REJECT_ALL"
    else:
        try:
            raw["best_candidate_index"] = max(1, min(3, int(bci)))
        except (TypeError, ValueError):
            raw["best_candidate_index"] = 1

    # confidence_score: float 0..100
    conf = raw.get("confidence_score", raw.get("coverage_score", 50.0))
    try:
        conf_f = float(conf)
        # AI đôi khi trả 0..1 thay vì 0..100
        if 0.0 <= conf_f <= 1.0:
            conf_f *= 100.0
        raw["confidence_score"] = max(0.0, min(100.0, conf_f))
    except (TypeError, ValueError):
        raw["confidence_score"] = 50.0

    # status: enforce business rule
    if raw["best_candidate_index"] == "REJECT_ALL":
        raw["status"] = "REJECTED"
    else:
        raw.setdefault(
            "status",
            "APPROVED" if raw["confidence_score"] >= 80 else "SUGGESTION",
        )
        if raw["status"] not in ("APPROVED", "SUGGESTION", "REJECTED"):
            raw["status"] = "APPROVED" if raw["confidence_score"] >= 80 else "SUGGESTION"

    # reasoning: inject structure if missing
    reasoning = str(raw.get("reasoning") or "")
    if "Điểm chưa khớp" not in reasoning:
        raw["reasoning"] = (
            "Điểm chưa khớp: (mô hình không trả về chi tiết)\n"
            f"Gợi ý hướng đi: {reasoning[:400]}\n"
            "Mã ICD thay thế: (không có)"
        )

    return raw


def safe_critic_parser(raw_response: str | None) -> dict[str, Any]:
    """
    Triple-Layer Parsing — không bao giờ trả về None.

    Layer 1 — JSON chuẩn (có strip markdown fence).
    Layer 2 — Regex recovery: móc best_candidate_index, confidence_score, status.
    Layer 3 — Hard-coded SUGGESTION fallback với cảnh báo bác sĩ.
    """
    if not raw_response or not isinstance(raw_response, str):
        return dict(_SAFE_FALLBACK)

    # ── Layer 1: Standard JSON ────────────────────────────────────────────────
    try:
        clean = re.sub(r"```(?:json)?|```", "", raw_response).strip()
        # Đôi khi AI trả nhiều dòng JSON — lấy đoạn từ '{' đến '}' đầu tiên
        brace_start = clean.find("{")
        brace_end   = clean.rfind("}")
        if brace_start != -1 and brace_end != -1:
            clean = clean[brace_start : brace_end + 1]
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return _normalize(parsed)
    except (json.JSONDecodeError, ValueError):
        print("[CRITIC] Layer-1 JSON fail — activating Regex Recovery...")

    # ── Layer 2: Regex Recovery ───────────────────────────────────────────────
    recovered: dict[str, Any] = {}

    # best_candidate_index
    m = re.search(
        r'"best_candidate_index"\s*:\s*("REJECT_ALL"|[1-3])',
        raw_response, re.IGNORECASE,
    )
    if m:
        val = m.group(1).strip('"')
        recovered["best_candidate_index"] = "REJECT_ALL" if val.upper() == "REJECT_ALL" else int(val)

    # confidence_score
    m = re.search(r'"confidence_score"\s*:\s*([0-9]+(?:\.[0-9]+)?)', raw_response)
    if m:
        recovered["confidence_score"] = float(m.group(1))

    # status
    m = re.search(
        r'"status"\s*:\s*"(APPROVED|SUGGESTION|REJECTED)"',
        raw_response, re.IGNORECASE,
    )
    if m:
        recovered["status"] = m.group(1).upper()

    # reasoning (best-effort)
    m = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_response)
    if m:
        recovered["reasoning"] = m.group(1).replace("\\n", "\n")

    if recovered:
        recovered.setdefault("best_candidate_index", 1)
        recovered.setdefault("confidence_score", 40.0)
        print(f"[CRITIC] Layer-2 Regex recovered: idx={recovered['best_candidate_index']} conf={recovered['confidence_score']}")
        return _normalize(recovered)

    # ── Layer 3: Hard-coded SUGGESTION fallback ───────────────────────────────
    print("[CRITIC] Layer-3 FALLBACK: returning safe SUGGESTION — bac si xac nhan thu cong.")
    return dict(_SAFE_FALLBACK)
