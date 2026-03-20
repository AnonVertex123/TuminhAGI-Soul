"""
nexus_core/output_formatter.py — TuminhAGI Output Layer V2.0
=============================================================
Transforms internal diagnosis data into a safe, structured, 4-section output.

Design principles:
- ZERO assertive diagnostic language ("Bạn bị...", "Chẩn đoán là...")
- All phrasing is descriptive/supportive: "Dấu hiệu này thường gặp trong..."
- 4 canonical sections: Symptom Summary, Possible Conditions, Urgency Triage, Doctor's Note
- Critic gate: suppresses output if similarity is low or domain contradictions are found
- Works as a pure transformation layer — does not touch core diagnostic logic
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# ── Urgency levels ────────────────────────────────────────────────────────────

URGENCY_EMERGENCY = "CẤP CỨU NGAY"
URGENCY_URGENT    = "Cần khám trong ngày"
URGENCY_WATCH     = "Theo dõi tại nhà"

# Red-flag ICD chapter prefixes that always escalate urgency
_EMERGENCY_CHAPTERS = frozenset(["I2", "I21", "I22",   # ACS / MI
                                   "G0", "G00", "G01",    # Meningitis / encephalitis
                                   "J9",  "J96",           # Respiratory failure
                                   "K25", "K26",           # GI perforation/bleeding
                                   "O00",                  # Ectopic pregnancy
                                   ])

# Symptom keywords that escalate urgency to URGENT even without red-flag ICD
_URGENT_KEYWORDS = frozenset([
    "chest pain", "đau ngực", "dau nguc",
    "shortness of breath", "khó thở", "kho tho",
    "neck stiffness", "cứng cổ", "cung co",
    "severe headache", "đau đầu dữ dội",
    "hematuria", "tiểu ra máu",
    "syncope", "ngất",
    "high fever", "sốt cao", "sot cao",
    "seizure", "co giật", "co giat",
])

# ── Descriptive phrase templates ──────────────────────────────────────────────

def _intro_phrase(icd_name: str, sim: float) -> str:
    """Build a non-assertive description phrase for one entity."""
    if sim >= 0.80:
        return f"Dấu hiệu này thường gặp trong các tình trạng liên quan đến **{icd_name}**."
    elif sim >= 0.60:
        return f"Có thể liên quan đến các tình trạng y khoa như **{icd_name}**."
    else:
        return f"Một trong những hướng cần khảo sát thêm là **{icd_name}** (mức độ tương đồng thấp — cần thêm dữ liệu)."


# ── Dataclass for structured output ──────────────────────────────────────────

@dataclass
class StructuredOutput:
    """4-section structured output for TuminhAGI V2.0."""
    symptom_summary: str       = ""   # Section 1
    possible_conditions: list  = field(default_factory=list)  # Section 2
    urgency: str               = URGENCY_WATCH                # Section 3
    urgency_reason: str        = ""
    doctor_note: str           = ""   # Section 4
    gate_passed: bool          = True
    gate_reason: str           = ""

    def to_dict(self) -> dict:
        return {
            "symptom_summary":     self.symptom_summary,
            "possible_conditions": self.possible_conditions,
            "urgency":             self.urgency,
            "urgency_reason":      self.urgency_reason,
            "doctor_note":         self.doctor_note,
            "gate_passed":         self.gate_passed,
            "gate_reason":         self.gate_reason,
        }

    def to_markdown(self) -> str:
        """Human-readable markdown for terminal / legacy UI."""
        if not self.gate_passed:
            return f"⛔ **Không thể đưa ra thông tin tham khảo**\nLý do: {self.gate_reason}"

        lines = []
        lines.append("---")
        lines.append("### [1] Tóm tắt triệu chứng")
        lines.append(self.symptom_summary)
        lines.append("")
        lines.append("### [2] Các khả năng có thể xảy ra")
        for item in self.possible_conditions:
            conf_tag = f" ({item['confidence']}%)" if item.get("confidence") else ""
            status_icon = {"APPROVED": "🟢", "SUGGESTION": "🟡", "EMERGENCY": "🔴"}.get(item.get("critic_status", ""), "⚪")
            lines.append(f"{status_icon} **{item['name']}**{conf_tag}")
            lines.append(f"   {item['description_phrase']}")
            if item.get("icd_reference"):
                lines.append(f"   _(Tham khảo: ICD-10 {item['icd_reference']})_")
            lines.append("")
        lines.append("### [3] Phân tầng mức độ nguy hiểm")
        urgency_icon = {"CẤP CỨU NGAY": "🚨", "Cần khám trong ngày": "⚠️", "Theo dõi tại nhà": "🟡"}.get(self.urgency, "ℹ️")
        lines.append(f"{urgency_icon} **{self.urgency}**")
        if self.urgency_reason:
            lines.append(f"   {self.urgency_reason}")
        lines.append("")
        lines.append("### [4] Bản tin cho Bác sĩ")
        lines.append("> " + self.doctor_note.replace("\n", "\n> "))
        lines.append("---")
        return "\n".join(lines)


# ── Critic gate ───────────────────────────────────────────────────────────────

def _critic_gate(diagnoses: list[dict], query: str) -> tuple[bool, str]:
    """
    Suppress output when:
    - All diagnoses have similarity < 0.38 AND status is not EMERGENCY
    - Any diagnosis has cross-domain contradiction (domain != ICD chapter)
    Returns (gate_passed, reason).
    """
    if not diagnoses:
        return False, "Không tìm được thực thể y khoa nào đáng tin cậy từ triệu chứng đã nhập."

    all_low_sim = all(d.get("score", 0) < 0.38 for d in diagnoses)
    any_emergency = any(
        str(d.get("code", "")).upper()[:3] in _EMERGENCY_CHAPTERS
        or any(kw in query.lower() for kw in _URGENT_KEYWORDS)
        for d in diagnoses
    )
    if all_low_sim and not any_emergency:
        avg = sum(d.get("score", 0) for d in diagnoses) / len(diagnoses)
        return (
            False,
            f"Độ tương đồng trung bình quá thấp ({avg:.2f} < 0.38). "
            "Vui lòng cung cấp thêm triệu chứng cụ thể để hệ thống đưa ra thông tin chính xác hơn.",
        )

    return True, ""


# ── Urgency triage ────────────────────────────────────────────────────────────

def _triage(diagnoses: list[dict], query: str, is_emergency_flag: bool) -> tuple[str, str]:
    """Determine urgency level and reason string."""
    query_lower = query.lower()
    codes_upper = [str(d.get("code", "")).upper() for d in diagnoses]

    # Emergency ICD codes
    for code in codes_upper:
        for pfx in _EMERGENCY_CHAPTERS:
            if code.startswith(pfx):
                return URGENCY_EMERGENCY, f"Mã ICD {code} thuộc nhóm bệnh lý nguy hiểm — cần can thiệp y tế khẩn cấp."

    # Emergency keyword in query
    if is_emergency_flag or any(kw in query_lower for kw in _URGENT_KEYWORDS):
        red_kws = [kw for kw in _URGENT_KEYWORDS if kw in query_lower]
        reason = f"Phát hiện dấu hiệu cảnh báo: {', '.join(red_kws[:3])}." if red_kws else "Phát hiện triệu chứng cấp tính."
        return URGENCY_URGENT, reason

    # SUGGESTION status from Critic
    if any(d.get("critic_status") == "SUGGESTION" for d in diagnoses):
        return URGENCY_WATCH, "Triệu chứng chưa rõ ràng — nên đặt lịch khám để được tư vấn trực tiếp."

    return URGENCY_WATCH, "Triệu chứng không thuộc nhóm cấp cứu — có thể theo dõi và khám định kỳ."


# ── Doctor's note builder ─────────────────────────────────────────────────────

def _doctor_note(query: str, diagnoses: list[dict], urgency: str) -> str:
    """
    Short paragraph the user can copy and hand to a real doctor.
    Uses only plain factual language, no self-diagnosis claims.
    """
    names = [d.get("name", d.get("code", "?")) for d in diagnoses]
    names_str = "; ".join(names[:3]) if names else "chưa xác định"
    codes_str = ", ".join(str(d.get("code", "")) for d in diagnoses[:3])

    note = (
        f"Người dùng mô tả triệu chứng: \"{query}\". "
        f"Hệ thống AI hỗ trợ đề xuất các nhóm bệnh cần khảo sát: {names_str} "
        f"(tham khảo ICD-10: {codes_str}). "
        f"Mức độ ưu tiên theo phân loại tự động: **{urgency}**. "
        "Đây là thông tin tham khảo — chẩn đoán chính thức thuộc thẩm quyền của Bác sĩ."
    )
    return note


# ── Main formatter function ───────────────────────────────────────────────────

def format_output(
    query: str,
    diagnoses: list[dict],
    parts: list[str],
    is_emergency: bool = False,
    status_label: str = "",
) -> StructuredOutput:
    """
    Entry point. Takes raw internal diagnosis data and produces StructuredOutput.

    Parameters
    ----------
    query       : original user query string
    diagnoses   : list of dicts with keys: code, name, score, critic_status,
                  critic_confidence, reasoning
    parts       : tokenized symptom parts
    is_emergency: flag from _is_emergency_case()
    status_label: from tuminh_multi_diagnostic_loop return value
    """
    out = StructuredOutput()

    # ── Critic gate ────────────────────────────────────────────────────────
    gate_ok, gate_reason = _critic_gate(diagnoses, query)
    if not gate_ok:
        out.gate_passed = False
        out.gate_reason = gate_reason
        return out

    # ── Section 1: Symptom Summary ────────────────────────────────────────
    parts_clean = [p for p in parts if p.strip()]
    if parts_clean:
        parts_joined = "; ".join(f"**{p}**" for p in parts_clean)
        out.symptom_summary = (
            f"Dựa trên mô tả của bạn, hệ thống nhận diện được các dấu hiệu sau: {parts_joined}. "
            "Đây là cách hiểu của AI từ ngôn ngữ tự nhiên — vui lòng xác nhận lại với bác sĩ nếu có điểm chưa chính xác."
        )
    else:
        out.symptom_summary = f"Hệ thống ghi nhận triệu chứng: \"{query}\"."

    # ── Section 2: Possible Conditions ───────────────────────────────────
    for d in diagnoses[:3]:
        icd_code  = str(d.get("code", ""))
        icd_name  = d.get("name", icd_code)
        sim       = float(d.get("score", 0))
        conf      = d.get("critic_confidence")
        c_status  = d.get("critic_status", "UNKNOWN")

        # Simplify ICD name: strip codes if embedded in string
        display_name = re.sub(r"\b[A-Z]\d{2}[\.\d]*\b", "", icd_name).strip(" -|")
        if not display_name:
            display_name = icd_name

        item = {
            "icd_reference":    icd_code,
            "name":             display_name,
            "description_phrase": _intro_phrase(display_name, sim),
            "similarity":       round(sim, 3),
            "confidence":       int(conf) if conf is not None else None,
            "critic_status":    c_status,
        }
        out.possible_conditions.append(item)

    # ── Section 3: Urgency Triage ─────────────────────────────────────────
    urgency, urgency_reason = _triage(diagnoses, query, is_emergency)

    # Override to EMERGENCY if status_label says so
    if status_label in ("EMERGENCY_WARN",) or is_emergency:
        if urgency != URGENCY_EMERGENCY:
            urgency = URGENCY_URGENT
            urgency_reason = urgency_reason or "Trường hợp cấp tính — cần đánh giá y tế ngay."

    out.urgency        = urgency
    out.urgency_reason = urgency_reason

    # ── Section 4: Doctor's Note ─────────────────────────────────────────
    out.doctor_note = _doctor_note(query, diagnoses, urgency)

    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Language Safety Guard
# ═══════════════════════════════════════════════════════════════════════════════

# Forbidden assertive phrases (from soul_vault/navigator_v2.txt)
_FORBIDDEN_PHRASES: list[tuple[str, str]] = [
    ("chắc chắn",       "có thể"),
    ("chẩn đoán là",    "gợi ý hướng"),
    ("bạn bị ",         "dấu hiệu có thể liên quan đến "),
    ("điều trị bằng",   "gợi ý hỗ trợ bằng"),
    ("kết luận rằng",   "có thể xem xét"),
    ("bạn mắc bệnh",    "dấu hiệu có thể gợi ý"),
]

# Required supportive phrases
_REQUIRED_PHRASES: frozenset[str] = frozenset([
    "có thể", "gợi ý", "tham khảo", "nên hỏi bác sĩ",
])


def _language_guard(text: str) -> str:
    """
    Enforce navigator language rules on a text string.

    - Replaces all forbidden phrases with safe equivalents (case-insensitive).
    - Never raises — always returns a safe string.
    - Logs when correction is made.
    """
    import logging
    _log = logging.getLogger("tuminh.formatter")
    result = text
    for forbidden, replacement in _FORBIDDEN_PHRASES:
        lower = result.lower()
        idx = lower.find(forbidden.lower())
        if idx != -1:
            original_slice = result[idx: idx + len(forbidden)]
            result = result[:idx] + replacement + result[idx + len(forbidden):]
            _log.warning(
                f"[LANGUAGE_GUARD] Replaced forbidden phrase "
                f"'{original_slice}' → '{replacement}'"
            )
    return result


def _guard_dict(d: dict) -> dict:
    """Recursively apply _language_guard to all string values in a dict."""
    out: dict = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k] = _language_guard(v)
        elif isinstance(v, dict):
            out[k] = _guard_dict(v)
        elif isinstance(v, list):
            out[k] = [
                _guard_dict(i) if isinstance(i, dict)
                else (_language_guard(i) if isinstance(i, str) else i)
                for i in v
            ]
        else:
            out[k] = v
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Treatment Output Formatter (V9.4 — with constitution section)
# ═══════════════════════════════════════════════════════════════════════════════

_DURATION_CAP = (
    "Dùng thử 1–2 tuần. Nếu không cải thiện hoặc triệu chứng nặng hơn "
    "→ đến khám bác sĩ ngay."
)

_TINH_LABELS: dict[str, str] = {
    "ôn":    "Ôn — tính ấm, phù hợp thể hàn",
    "nhiệt": "Nhiệt — tính nóng, tránh thể nhiệt",
    "hàn":   "Hàn — tính lạnh, phù hợp thể nhiệt",
    "lương": "Lương — tính mát, phù hợp thể nhiệt",
    "bình":  "Bình — tính trung tính, phù hợp mọi thể",
    "táo":   "Táo — tính khô, tránh thể âm hư",
}


def format_treatment_output(decision: Any) -> dict:
    """
    Transform a TreatmentDecision (V9.4) into a frontend-ready dict.

    Always includes:
      - constitution section
      - duration_cap (1-2 week warning)
      - evidence label per herb
      - disclaimer
      - language guard on all text fields

    Returns
    -------
    {
      "track": str,
      "sections": [...],
      "constitution": {...},
      "safety_warnings": [...],
      "duration_cap": str,
      "warning": str,
      "disclaimer": str,
      "emergency_banner": bool,
      "pending_questions": [...] | null
    }
    """
    track: str      = getattr(decision, "track", "western_only")
    urgency: str    = getattr(decision, "urgency", "routine")
    herbal: list    = getattr(decision, "herbal_options", []) or []
    western: list   = getattr(decision, "western_options", []) or []
    warning: str    = getattr(decision, "warning", "")
    disclaimer: str = getattr(decision, "disclaimer",
                               "Thông tin chỉ mang tính tham khảo — không thay thế bác sĩ.")
    constitution_type = getattr(decision, "constitution_type", None)
    constitution_note_str = getattr(decision, "constitution_note", "")
    pending_qs = getattr(decision, "pending_questions", []) or []
    safety_warnings = getattr(decision, "safety_warnings", []) or []
    duration_cap = getattr(decision, "duration_cap", _DURATION_CAP)

    is_emergency  = track == "emergency"
    has_pending   = bool(pending_qs)

    # ── Format each herb with evidence label and tinh label ─────────────────
    def _enrich_herb(h: dict) -> dict:
        ev    = h.get("evidence_level", "low")
        tinh  = h.get("tinh", "bình")
        return {
            **h,
            "evidence":  h.get("evidence_label") or (
                "Có nghiên cứu lâm sàng"          if ev == "high"
                else "Kinh nghiệm dân gian, chưa đủ bằng chứng" if ev == "medium"
                else "Truyền thống — chưa có nghiên cứu"
            ),
            "tinh_label": _TINH_LABELS.get(tinh, f"Tính {tinh}"),
        }

    enriched_herbal = [_enrich_herb(h) for h in herbal]

    # ── Sections ─────────────────────────────────────────────────────────────
    herbal_section = {
        "type":     "herbal",
        "title":    "Thuốc Nam gợi ý",
        "subtitle": "Theo GS. Đỗ Tất Lợi — ưu tiên lành tính, phù hợp thể trạng",
        "items":    enriched_herbal,
        "visible":  bool(enriched_herbal) and not is_emergency and not has_pending,
        "badge":    "Nam Y",
        "badge_color": "emerald",
    }

    western_section = {
        "type":     "western",
        "title":    "Tây y tham khảo",
        "subtitle": "Cần tư vấn bác sĩ trước khi dùng — đây là thông tin tham khảo",
        "items":    western,
        "visible":  bool(western) and (is_emergency or track in ("both", "western_only")),
        "badge":    "Tây Y",
        "badge_color": "blue",
    }

    # ── Constitution section ──────────────────────────────────────────────────
    if constitution_type is not None:
        c_value = getattr(constitution_type, "value", str(constitution_type))
    else:
        c_value = "Chưa xác định"

    constitution_section = {
        "type":              c_value,
        "note":              constitution_note_str or f"Thể trạng: {c_value}",
        "questions_pending": has_pending,
        "questions":         pending_qs,
    }

    # ── Build raw output ──────────────────────────────────────────────────────
    raw = {
        "track":            track,
        "urgency":          urgency,
        "sections":         [herbal_section, western_section],
        "constitution":     constitution_section,
        "safety_warnings":  safety_warnings,
        "duration_cap":     duration_cap,
        "warning":          warning,
        "disclaimer":       disclaimer,
        "emergency_banner": is_emergency,
        "pending_questions": pending_qs if has_pending else None,
    }

    # ── Apply language guard to all text values ───────────────────────────────
    return _guard_dict(raw)
