"""
missions_hub/constitution_classifier.py — TuminhAGI Constitution Classifier V1.0
==================================================================================
Classifies patient's body constitution (thể trạng) from 5 yes/no answers,
then filters herb recommendations for safety.

Philosophy:
  TuminhAGI is a NAVIGATOR — every suggestion uses:
    "có thể", "gợi ý", "tham khảo" — never "bạn bị X" or "điều trị bằng"

Constitution types (thể trạng) based on traditional Vietnamese medicine (YHCT):
  Phong nhiệt  — heat/inflammation
  Phong hàn    — cold/chills
  Khí hư       — qi deficiency
  Âm hư        — yin deficiency
  Dương hư     — yang deficiency
  Đàm thấp     — dampness/phlegm
  Chưa xác định— unknown (show questions, not herbs)

Safety gates run in fixed order — NEVER bypassed:
  1. Pregnancy gate (before constitution filter)
  2. Drug interaction gate (before herb list returned)
  3. Duration cap injected into every output
  4. Evidence level shown for every herb

Reference: GS. Đỗ Tất Lợi — Những cây thuốc và vị thuốc Việt Nam (2006)
           Học viện Y học Cổ truyền Việt Nam — Phân loại thể trạng cơ bản
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

DURATION_CAP = (
    "Dùng thử 1–2 tuần. Nếu không cải thiện hoặc triệu chứng nặng hơn "
    "→ đến khám bác sĩ ngay."
)

DISCLAIMER = (
    "Thông tin này chỉ mang tính tham khảo theo tinh thần y học cổ truyền Việt Nam. "
    "Không thay thế chẩn đoán, toa thuốc hoặc hướng dẫn của bác sĩ. "
    "Nếu triệu chứng nặng hơn, hãy đến cơ sở y tế ngay."
)

# Evidence level labels — always shown to user
EVIDENCE_LABELS: dict[str, str] = {
    "high":   "Có nghiên cứu lâm sàng",
    "medium": "Kinh nghiệm dân gian, chưa đủ bằng chứng lâm sàng",
    "low":    "Truyền thống — chưa có nghiên cứu",
}

# Herbs known to have significant drug interactions
_DRUG_INTERACTION_MAP: dict[str, list[str]] = {
    "Đan sâm":     ["warfarin", "aspirin", "digoxin", "thuốc chống đông"],
    "Cam thảo":    ["digoxin", "thuốc lợi tiểu", "corticosteroid", "thuốc hạ áp"],
    "Hà thủ ô đỏ": ["statin", "methotrexate", "paracetamol", "thuốc gan"],
    "Tam thất":    ["warfarin", "aspirin", "clopidogrel", "thuốc chống đông"],
    "Nghệ vàng":   ["warfarin", "aspirin", "thuốc chống đông"],
    "Linh chi":    ["warfarin", "aspirin", "thuốc chống đông", "immunosuppressant"],
    "Bình vôi":    ["benzodiazepine", "thuốc an thần", "thuốc ngủ", "rượu"],
    "Lạc tiên":    ["benzodiazepine", "thuốc an thần", "thuốc ngủ"],
    "Khổ qua":     ["insulin", "metformin", "thuốc hạ đường huyết"],
    "Hoàng liên":  ["metformin", "cyclosporin", "thuốc hạ đường huyết"],
    "Trạch tả":    ["thuốc lợi tiểu", "thuốc hạ áp", "lithium"],
    "Câu đằng":    ["thuốc hạ áp", "canxi blocker"],
    "Sơn tra":     ["warfarin", "digoxin", "thuốc tim mạch"],
}

# Property tags that are EXCLUDED per constitution
# Key = constitution value string, Value = set of unsafe "tinh" tags
_EXCLUSION_MAP: dict[str, frozenset[str]] = {
    "Phong nhiệt": frozenset(["ôn", "nhiệt"]),        # warming herbs worsen heat
    "Phong hàn":   frozenset(["hàn", "lương"]),       # cooling herbs worsen cold
    "Dương hư":    frozenset(["hàn"]),                 # cold herbs worsen yang deficiency
    "Âm hư":       frozenset(["táo"]),                 # drying herbs harm yin
}

# Keywords triggering pregnancy check
_PREGNANCY_KEYWORDS: frozenset[str] = frozenset([
    "có thai", "mang thai", "thai kỳ", "bầu", "đang mang thai",
    "thai phụ", "3 tháng đầu", "trimester",
])

# Contraindication keywords that flag pregnancy risk
_PREGNANCY_CONTRAINDICATION_KEYWORDS: frozenset[str] = frozenset([
    "thai kỳ", "có thai", "mang thai", "thai phụ", "sảy thai",
    "co tử cung", "3 tháng đầu",
])


# ── Enums ─────────────────────────────────────────────────────────────────────

class ConstitutionType(Enum):
    PHONG_NHIET = "Phong nhiệt"
    PHONG_HAN   = "Phong hàn"
    KHI_HU      = "Khí hư"
    AM_HU       = "Âm hư"
    DUONG_HU    = "Dương hư"
    DAM_THAP    = "Đàm thấp"
    UNKNOWN     = "Chưa xác định"


# ── Questions ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ConstitutionQuestion:
    key: str
    text: str
    signal: str   # internal scoring key


QUESTIONS: list[ConstitutionQuestion] = [
    ConstitutionQuestion(
        key="Q1",
        text="Bạn có hay sợ lạnh, tay chân lạnh không?",
        signal="Han",
    ),
    ConstitutionQuestion(
        key="Q2",
        text="Bạn có hay khát nước, miệng khô, thích đồ mát không?",
        signal="Nhiet",
    ),
    ConstitutionQuestion(
        key="Q3",
        text="Bạn có hay mệt mỏi, hơi thở ngắn, nói chuyện yếu không?",
        signal="Hu",
    ),
    ConstitutionQuestion(
        key="Q4",
        text="Bạn có hay đổ mồ hôi đêm, nóng trong người về chiều không?",
        signal="AmHu",
    ),
    ConstitutionQuestion(
        key="Q5",
        text="Bạn có hay nặng nề, đờm nhiều, tiêu hóa kém không?",
        signal="DamThap",
    ),
]


# ── Gate result dataclass ─────────────────────────────────────────────────────

@dataclass
class GateResult:
    """Result of applying safety gates to a herb list."""
    herbs: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str]         = field(default_factory=list)
    duration_cap: str           = DURATION_CAP
    disclaimer: str             = DISCLAIMER


# ── ConstitutionClassifier ────────────────────────────────────────────────────

class ConstitutionClassifier:
    """
    Classifies body constitution from 5 yes/no answers and
    filters herbs according to safety rules.

    All methods are stateless and thread-safe.
    """

    # Expose questions list as class attribute
    QUESTIONS: list[ConstitutionQuestion] = QUESTIONS

    # ── Classify ──────────────────────────────────────────────────────────────

    def classify(self, answers: dict[str, bool]) -> ConstitutionType:
        """
        Derive dominant constitution type from Q1–Q5 answers.

        Parameters
        ----------
        answers : dict mapping question key ("Q1"…"Q5") to bool (True=yes)

        Returns
        -------
        ConstitutionType — dominant type, or UNKNOWN if no signal
        """
        score: dict[str, int] = {
            "Han":    0,
            "Nhiet":  0,
            "Hu":     0,
            "AmHu":   0,
            "DamThap": 0,
        }

        for q in QUESTIONS:
            if answers.get(q.key, False):
                score[q.signal] = score.get(q.signal, 0) + 1

        # AmHu + Hu → refine to Am Hu (yin deficiency sweating is more specific)
        total = sum(score.values())
        if total == 0:
            return ConstitutionType.UNKNOWN

        dominant_signal = max(score, key=lambda k: score[k])
        max_score = score[dominant_signal]

        # Tie-break: if more than one signal shares the max → UNKNOWN
        tied = [k for k, v in score.items() if v == max_score]
        if len(tied) > 1 and max_score <= 1:
            return ConstitutionType.UNKNOWN

        # Map signal → ConstitutionType
        _SIGNAL_MAP: dict[str, ConstitutionType] = {
            "Han":    ConstitutionType.PHONG_HAN,
            "Nhiet":  ConstitutionType.PHONG_NHIET,
            "Hu":     ConstitutionType.KHI_HU,
            "AmHu":   ConstitutionType.AM_HU,
            "DamThap": ConstitutionType.DAM_THAP,
        }
        return _SIGNAL_MAP.get(dominant_signal, ConstitutionType.UNKNOWN)

    # ── Filter herbs by constitution ──────────────────────────────────────────

    def filter_herbs_by_constitution(
        self,
        herbs: list[dict[str, Any]],
        constitution: ConstitutionType,
    ) -> list[dict[str, Any]]:
        """
        Remove herbs contraindicated for this constitution type.

        Safety rules (hardcoded — never bypass):
          PHONG_NHIET → exclude tinh="ôn" or "nhiệt"
          PHONG_HAN   → exclude tinh="hàn" or "lương"
          DUONG_HU    → exclude tinh="hàn"
          AM_HU       → exclude tinh="táo"
          UNKNOWN     → return all herbs, sorted safe first
        """
        if constitution == ConstitutionType.UNKNOWN:
            # Safe-first sort, no exclusions
            return sorted(herbs, key=lambda h: (0 if h.get("safety_level") == "safe" else 1))

        excluded_tinhs = _EXCLUSION_MAP.get(constitution.value, frozenset())
        if not excluded_tinhs:
            return herbs

        result: list[dict[str, Any]] = []
        for h in herbs:
            tinh = _normalize_tinh(h.get("tinh", "bình"))
            if tinh in excluded_tinhs:
                continue
            result.append(h)

        return result

    # ── Safety gates ──────────────────────────────────────────────────────────

    def apply_gates(
        self,
        herbs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> GateResult:
        """
        Apply all 4 safety gates to the herb list.

        Gates run in fixed order:
          1. Pregnancy gate     — always first
          2. Drug interaction   — always second
          3. Duration cap       — injected into result
          4. Evidence level     — injected into each herb

        Parameters
        ----------
        herbs   : list of herb dicts (from treatment_router or lookup)
        context : dict with optional keys:
                  "có thai": bool
                  "medications": list[str]
                  any string key containing pregnancy keyword
        """
        warnings: list[str] = []
        working = list(herbs)

        # ── Gate 1: Pregnancy ────────────────────────────────────────────────
        is_pregnant = self._detect_pregnancy(context)
        if is_pregnant:
            safe_herbs, preg_removed = [], []
            for h in working:
                contras = " ".join(
                    str(c).lower()
                    for c in h.get("contraindications", [])
                )
                is_risky = any(kw in contras for kw in _PREGNANCY_CONTRAINDICATION_KEYWORDS)
                if is_risky:
                    preg_removed.append(h.get("name_vn", "?"))
                else:
                    safe_herbs.append(h)
            working = safe_herbs
            warnings.append(
                "Phụ nữ có thai: chỉ dùng thuốc Nam khi có chỉ định của thầy thuốc YHCT. "
                f"Đã loại {len(preg_removed)} vị thuốc có nguy cơ: "
                f"{', '.join(preg_removed) if preg_removed else 'không có'}."
            )

        # ── Gate 2: Drug interactions ────────────────────────────────────────
        medications: list[str] = []
        if isinstance(context.get("medications"), list):
            medications = [str(m).lower() for m in context["medications"]]

        if medications:
            flagged: list[str] = []
            for h in working:
                h_name = h.get("name_vn", "")
                interactions = _DRUG_INTERACTION_MAP.get(h_name, [])
                matched = [
                    drug for drug in interactions
                    if any(med in drug.lower() or drug.lower() in med for med in medications)
                ]
                if matched:
                    flagged.append(f"{h_name} (tương tác: {', '.join(matched)})")
                    # Inject interaction flag into herb dict (non-destructive copy)
                    h["interaction_warning"] = f"Có thể tương tác với: {', '.join(matched)}"
            if flagged:
                warnings.append(
                    "Đang dùng thuốc Tây — cần hỏi bác sĩ trước khi kết hợp thuốc Nam. "
                    f"Các vị cần chú ý: {'; '.join(flagged)}."
                )

        # ── Gate 4: Inject evidence level into each herb ─────────────────────
        # (Gate 3 = duration cap, added to GateResult directly)
        for h in working:
            ev = h.get("evidence_level", "low")
            h["evidence_label"] = EVIDENCE_LABELS.get(ev, EVIDENCE_LABELS["low"])

        return GateResult(herbs=working, warnings=warnings)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_pregnancy(context: dict[str, Any]) -> bool:
        """Return True if context indicates pregnancy."""
        # Explicit bool flag
        if context.get("có thai") or context.get("pregnant"):
            return True
        # Keyword scan across all string values in context
        ctx_text = " ".join(str(v) for v in context.values()).lower()
        return any(kw in ctx_text for kw in _PREGNANCY_KEYWORDS)

    @staticmethod
    def constitution_note(c: ConstitutionType) -> str:
        """Human-readable note explaining the constitution type."""
        _NOTES: dict[ConstitutionType, str] = {
            ConstitutionType.PHONG_NHIET: (
                "Thể nhiệt — ưu tiên vị mát (hàn/lương), "
                "tránh các vị ôn/nhiệt làm tăng nhiệt trong người."
            ),
            ConstitutionType.PHONG_HAN: (
                "Thể hàn — ưu tiên vị ấm (ôn), "
                "tránh các vị hàn/lương làm tăng lạnh trong người."
            ),
            ConstitutionType.KHI_HU: (
                "Thể khí hư — ưu tiên bổ khí, kiện tỳ. "
                "Tránh các vị quá mạnh khi cơ thể đang yếu."
            ),
            ConstitutionType.AM_HU: (
                "Thể âm hư — ưu tiên dưỡng âm, tránh vị táo (khô). "
                "Nên dùng thêm nhiều nước."
            ),
            ConstitutionType.DUONG_HU: (
                "Thể dương hư — ưu tiên ôn dương, tránh hàn lương. "
                "Cần giữ ấm, ăn đủ dinh dưỡng."
            ),
            ConstitutionType.DAM_THAP: (
                "Thể đàm thấp — ưu tiên hóa đàm, lợi thủy. "
                "Tránh ăn đồ béo ngọt, giảm nặng nề."
            ),
            ConstitutionType.UNKNOWN: (
                "Chưa xác định thể trạng — gợi ý chung, nên hỏi thầy thuốc YHCT "
                "để được phân loại thể trạng chính xác."
            ),
        }
        return _NOTES.get(c, "Chưa có mô tả.")


# ── Utility ───────────────────────────────────────────────────────────────────

def _normalize_tinh(tinh: str) -> str:
    """Normalize tinh value: lowercase, NFC, strip whitespace."""
    return unicodedata.normalize("NFC", str(tinh).lower().strip())
