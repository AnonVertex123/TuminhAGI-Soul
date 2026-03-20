"""
missions_hub/treatment_router.py — TuminhAGI Treatment Router V1.0
====================================================================
Routes each diagnosis to the appropriate treatment track.

Philosophy (Hải Thượng Lãn Ông / Navigator V2.0):
  Track A — Thuốc Nam (Vietnamese herbal medicine, GS. Đỗ Tất Lợi)
             FIRST choice for mild/chronic conditions — safe, no side effects
  Track B — Tây y (Western medicine)
             MANDATORY when emergency/red flag detected

Rules:
  1. Emergency            → western_only (herbal_options=[])
  2. Routine + mild       → herbal_only (if herbs found) else both + warning
  3. Urgent or moderate   → both tracks
  4. No herb data found   → always warn, add western fallback

Stateless: no global mutable state. TreatmentRouter instances are thread-safe.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

# ── V9.4: Constitution Classifier (lazy import) ───────────────────────────────
try:
    from missions_hub.constitution_classifier import (
        ConstitutionClassifier as _ConstitutionClassifier,
        ConstitutionType,
        QUESTIONS as _QUESTIONS,
        DURATION_CAP,
    )
    _CLASSIFIER_AVAILABLE = True
    _classifier = _ConstitutionClassifier()
except Exception as _cc_err:
    _CLASSIFIER_AVAILABLE = False
    _classifier = None  # type: ignore
    ConstitutionType = None  # type: ignore
    _QUESTIONS = []
    DURATION_CAP = "Dùng thử 1–2 tuần. Nếu không cải thiện → khám bác sĩ ngay."

# ── Constants ─────────────────────────────────────────────────────────────────

DISCLAIMER = (
    "Thông tin này chỉ mang tính tham khảo theo tinh thần y học cổ truyền Việt Nam. "
    "Không thay thế chẩn đoán, toa thuốc hoặc hướng dẫn của bác sĩ. "
    "Nếu triệu chứng nặng hơn, hãy đến cơ sở y tế ngay."
)

# ICD codes that are ABSOLUTE emergency — never show herbal medicine
_EMERGENCY_CODES: frozenset[str] = frozenset([
    "I21", "I22",   # STEMI / NSTEMI
    "I63", "I61", "I64",  # Stroke
    "I26",          # Pulmonary embolism
    "G41",          # Status epilepticus
    "K92",          # GI hemorrhage
    "J96",          # Respiratory failure
    "O00",          # Ectopic pregnancy
])

_EMERGENCY_CHAPTERS: frozenset[str] = frozenset(["I2", "I6"])
# Note: G41 (status epilepticus) is in _EMERGENCY_CODES; avoid over-broad G4 prefix
# to allow G43 (migraine) and G47 (sleep disorders) to receive herbal support

# Standard Western referral templates per ICD chapter
_WESTERN_REFERRALS: dict[str, dict[str, str]] = {
    "I": {"approach": "Khám tim mạch", "referral_type": "Bệnh viện / Phòng khám tim mạch",
          "notes": "Đo ECG, xét nghiệm men tim, siêu âm tim nếu cần."},
    "G": {"approach": "Khám thần kinh", "referral_type": "Bệnh viện / Phòng khám thần kinh",
          "notes": "CT/MRI não nếu nghi ngờ đột quỵ hoặc viêm màng não."},
    "J": {"approach": "Khám hô hấp", "referral_type": "Phòng khám nội / Hô hấp",
          "notes": "Xquang phổi, đo SpO2, spirometry nếu hen/COPD."},
    "K": {"approach": "Khám tiêu hóa", "referral_type": "Phòng khám nội / Tiêu hóa",
          "notes": "Nội soi dạ dày nếu đau thượng vị kéo dài."},
    "N": {"approach": "Khám tiết niệu / Phụ khoa", "referral_type": "Phòng khám tiết niệu hoặc sản phụ khoa",
          "notes": "Xét nghiệm nước tiểu, siêu âm bụng."},
    "O": {"approach": "Khám sản phụ khoa KHẨN", "referral_type": "Bệnh viện sản",
          "notes": "Siêu âm thai, xét nghiệm beta-hCG. Không trì hoãn."},
    "M": {"approach": "Khám cơ xương khớp", "referral_type": "Phòng khám nội / Cơ xương khớp",
          "notes": "X-quang khớp, xét nghiệm RF/anti-CCP nếu nghi viêm khớp dạng thấp."},
    "F": {"approach": "Khám tâm thần kinh", "referral_type": "Phòng khám tâm thần",
          "notes": "Đánh giá GAD-7, PHQ-9. Liệu pháp nhận thức hành vi (CBT)."},
    "E": {"approach": "Khám nội tiết", "referral_type": "Phòng khám nội / Nội tiết",
          "notes": "Xét nghiệm HbA1c, đường huyết lúc đói."},
    "D": {"approach": "Khám huyết học", "referral_type": "Phòng khám nội / Huyết học",
          "notes": "Công thức máu toàn phần (CBC), sắt huyết thanh, ferritin."},
    "L": {"approach": "Khám da liễu", "referral_type": "Phòng khám da liễu",
          "notes": "Không tự dùng corticoid mà không có chỉ định bác sĩ."},
    "R": {"approach": "Khám bác sĩ đa khoa", "referral_type": "Phòng khám đa khoa",
          "notes": "Xét nghiệm cơ bản theo triệu chứng."},
    "Z": {"approach": "Khám sức khỏe tổng quát", "referral_type": "Phòng khám đa khoa",
          "notes": "Xét nghiệm định kỳ, tư vấn lối sống."},
}

_DEFAULT_WESTERN = {"approach": "Khám bác sĩ đa khoa", "referral_type": "Phòng khám đa khoa",
                    "notes": "Mô tả triệu chứng đầy đủ để bác sĩ đánh giá."}

_HERB_DATA_PATH = Path(__file__).parent.parent / "data" / "tuminh_herb_encyclopedia.jsonl"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class TreatmentDecision:
    """
    Result of TreatmentRouter.decide().

    track:
      "emergency"   — go to hospital immediately, no herbal options
      "herbal_only" — mild/chronic: herbal medicine first
      "both"        — moderate/urgent: show both options
      "western_only"— no herb data available
    """
    track: str                           # "emergency"|"herbal_only"|"both"|"western_only"
    urgency: str                         # "emergency"|"urgent"|"routine"
    herbal_options: list[dict[str, Any]] = field(default_factory=list)
    western_options: list[dict[str, Any]] = field(default_factory=list)
    warning: str       = ""
    disclaimer: str    = DISCLAIMER
    # V9.4 constitution fields
    constitution_type: Any  = None       # ConstitutionType enum or None
    constitution_note: str  = ""
    pending_questions: list = field(default_factory=list)  # non-empty → no herbs yet
    safety_warnings: list[str] = field(default_factory=list)
    duration_cap: str = DURATION_CAP


# ── Herb loader (cached) ──────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_herb_db() -> tuple[dict, ...]:
    """Load herb encyclopedia once, cache as immutable tuple of dicts."""
    if not _HERB_DATA_PATH.exists():
        return ()
    herbs = []
    with open(_HERB_DATA_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    herbs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return tuple(herbs)


def _format_herb(h: dict) -> dict[str, Any]:
    """Slim projection for frontend consumption — includes V9.4 constitution fields."""
    return {
        "herb_id":           h.get("herb_id", ""),
        "name_vn":           h.get("name_vn", ""),
        "name_latin":        h.get("name_latin", ""),
        "nhom":              h.get("nhom", ""),
        "usage":             h.get("usage", ""),
        "dosage":            h.get("dosage", ""),
        "contraindications": h.get("contraindications", []),
        "safety_level":      h.get("safety_level", "safe"),
        "conditions_vn":     h.get("conditions_vn", []),
        "notes":             h.get("notes", ""),
        # V9.4 fields
        "tinh":              h.get("tinh", "bình"),
        "evidence_level":    h.get("evidence_level", "low"),
        "evidence_label":    h.get("evidence_label", "Truyền thống — chưa có nghiên cứu"),
        "drug_interactions": h.get("drug_interactions", []),
        "interaction_warning": h.get("interaction_warning", ""),
    }


def _lookup_herbs(disease_id: str) -> list[dict[str, Any]]:
    """
    Find herbs relevant to disease_id.

    Matching strategy (priority order):
      1. Exact ICD-10 code in herb's icd10_codes list
      2. ICD-10 chapter prefix match (first 1-3 chars) in herb's icd10_codes
      3. ICD-10 chapter letter in herb's icd10_chapters list
    """
    herbs = _load_herb_db()
    if not herbs:
        return []

    disease_id = disease_id.strip().upper()
    chap = disease_id[0] if disease_id else ""

    exact: list[dict] = []
    prefix: list[dict] = []
    chapter: list[dict] = []

    for h in herbs:
        codes: list[str] = [c.upper() for c in h.get("icd10_codes", [])]
        chapters: list[str] = [c.upper() for c in h.get("icd10_chapters", [])]

        if disease_id in codes:
            exact.append(h)
        elif any(disease_id.startswith(c) or c.startswith(disease_id[:2]) for c in codes):
            prefix.append(h)
        elif chap in chapters:
            chapter.append(h)

    # Combine, deduplicate, limit to 5
    seen: set[str] = set()
    result: list[dict] = []
    for h in (exact + prefix + chapter):
        hid = h.get("herb_id", "")
        if hid not in seen:
            seen.add(hid)
            result.append(_format_herb(h))
        if len(result) >= 5:
            break

    return result


def _lookup_western(disease_id: str) -> list[dict[str, Any]]:
    """Return standard western treatment reference for this ICD code."""
    chap = (disease_id or "R")[0].upper()
    referral = _WESTERN_REFERRALS.get(chap, _DEFAULT_WESTERN)
    return [{**referral, "icd_reference": disease_id}]


def _is_absolute_emergency(disease_id: str) -> bool:
    """True if this ICD code is always emergency regardless of urgency param."""
    d = disease_id.strip().upper()
    if d in _EMERGENCY_CODES:
        return True
    for pfx in _EMERGENCY_CHAPTERS:
        if d.startswith(pfx):
            return True
    return False


# ── TreatmentRouter ───────────────────────────────────────────────────────────

class TreatmentRouter:
    """
    Stateless treatment decision engine.

    Usage:
        router = TreatmentRouter()
        decision = router.decide("K25", urgency="routine", symptom_severity="nhẹ")
        print(decision.track, decision.herbal_options)
    """

    def decide(
        self,
        disease_id: str,
        urgency: str,
        symptom_severity: str = "",
        constitution_answers: dict[str, bool] | None = None,
        context: dict[str, Any] | None = None,
    ) -> TreatmentDecision:
        """
        Route diagnosis to treatment track.

        Parameters
        ----------
        disease_id           : ICD-10 code (e.g. "K25", "I21")
        urgency              : "emergency" | "urgent" | "routine"
        symptom_severity     : "nhẹ" | "vừa" | "nặng" | "rất nặng" | ""
        constitution_answers : dict Q1..Q5 → bool, or None (ask questions first)
        context              : dict with optional: "medications", "có thai", etc.
        """
        disease_id = (disease_id or "").strip().upper()
        urgency    = (urgency or "routine").lower()
        severity   = (symptom_severity or "").strip().lower()
        ctx        = dict(context or {})

        # ── RULE 1: Emergency — classifier never runs, safety first ────────
        if urgency == "emergency" or _is_absolute_emergency(disease_id):
            return TreatmentDecision(
                track="emergency",
                urgency="emergency",
                herbal_options=[],
                western_options=_lookup_western(disease_id),
                warning=(
                    "🚨 TÌNH TRẠNG NGUY HIỂM — Cần đến bệnh viện NGAY. "
                    "Không tự điều trị bằng thuốc Nam hay bất kỳ loại thuốc nào. "
                    "Gọi cấp cứu 115 nếu cần."
                ),
            )

        # ── RULE 2: No constitution answers → ask 5 questions first ────────
        if _CLASSIFIER_AVAILABLE and constitution_answers is None:
            return TreatmentDecision(
                track="herbal_only",   # track intent, but no herbs yet
                urgency=urgency,
                herbal_options=[],     # empty until questions answered
                western_options=[],
                pending_questions=[
                    {"key": q.key, "text": q.text} for q in _QUESTIONS
                ],
                warning=(
                    "Để gợi ý thuốc Nam phù hợp với thể trạng, "
                    "vui lòng trả lời 5 câu hỏi ngắn bên dưới."
                ),
            )

        # ── Get herbs for this disease ─────────────────────────────────────
        herbs = _lookup_herbs(disease_id)

        # ── Apply constitution filter ───────────────────────────────────────
        constitution_type = None
        constitution_note_str = ""
        if _CLASSIFIER_AVAILABLE and constitution_answers is not None:
            constitution_type = _classifier.classify(constitution_answers)
            constitution_note_str = _classifier.constitution_note(constitution_type)
            herbs = _classifier.filter_herbs_by_constitution(herbs, constitution_type)

        # ── Apply safety gates (pregnancy, drug interactions) ──────────────
        safety_warnings: list[str] = []
        if _CLASSIFIER_AVAILABLE and herbs:
            gate_result = _classifier.apply_gates(herbs, ctx)
            herbs = gate_result.herbs
            safety_warnings = gate_result.warnings

        # ── RULE 3: Routine + mild/moderate ────────────────────────────────
        if urgency == "routine" and severity in ("nhẹ", "vừa", ""):
            if herbs:
                return TreatmentDecision(
                    track="herbal_only",
                    urgency="routine",
                    herbal_options=herbs,
                    western_options=[],
                    warning=(
                        "Thuốc Nam được gợi ý theo GS. Đỗ Tất Lợi cho tình trạng nhẹ/mạn tính. "
                        "Nếu không cải thiện sau 1–2 tuần, hãy đến khám bác sĩ."
                    ),
                    constitution_type=constitution_type,
                    constitution_note=constitution_note_str,
                    safety_warnings=safety_warnings,
                )
            else:
                return TreatmentDecision(
                    track="both",
                    urgency="routine",
                    herbal_options=[],
                    western_options=_lookup_western(disease_id),
                    warning=(
                        "Chưa có dữ liệu thuốc Nam phù hợp cho bệnh này — "
                        "gợi ý tham khảo Tây y kèm theo."
                    ),
                    constitution_type=constitution_type,
                    constitution_note=constitution_note_str,
                    safety_warnings=safety_warnings,
                )

        # ── RULE 4: Urgent or severe ────────────────────────────────────────
        western = _lookup_western(disease_id)
        warning_parts: list[str] = []

        if herbs:
            warning_parts.append(
                "Thuốc Nam có thể hỗ trợ bồi bổ và giảm triệu chứng nhẹ."
            )
        else:
            warning_parts.append(
                "Chưa có dữ liệu thuốc Nam — ưu tiên tham khảo Tây y."
            )
        warning_parts.append(
            "Tình trạng ở mức cần theo dõi — hãy tham khảo bác sĩ để được đánh giá chính xác."
        )

        return TreatmentDecision(
            track="both",
            urgency=urgency,
            herbal_options=herbs,
            western_options=western,
            warning=" ".join(warning_parts),
            constitution_type=constitution_type,
            constitution_note=constitution_note_str,
            safety_warnings=safety_warnings,
        )
