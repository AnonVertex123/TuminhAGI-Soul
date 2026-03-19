"""
nexus_core/strict_validator.py — MedicalGatekeeper V1.0
========================================================
4-layer protection against hallucination and wrong-domain ICD mapping.

Layer 1 — Canonical Mapping  : VN → standard Medical English (no LLM)
Layer 2 — Term Validation     : check against curated MeSH-subset whitelist
Layer 3 — Domain Lock         : ICD chapter must match symptom's specialty
Layer 4 — Reverse Sim Check   : cosine(ICD_desc, symptom) >= threshold

Design principles (from TUMINH_BRAIN):
- Hard mapping beats LLM translation (0ms vs 30s, deterministic)
- Domain lock before embedding (prevents G40 for "trễ kinh")
- Thresholds are adaptive: RED_FLAG=0.33, standard=0.38 (V5.2)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Layer 1: Canonical Mapping ───────────────────────────────────────────────
# Format: "vn_variant" -> {"en": "standard MeSH term", "domain": "SPECIALTY",
#                          "icd_prefixes": ["N","O",...]}
# Include all encoding/diacritic variants to survive cp1252 corruption.

CANONICAL_MAP: dict[str, dict[str, Any]] = {
    # ── OB/GYN ──────────────────────────────────────────────────────────────
    "trễ kinh":              {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "tre kinh":              {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "trẽ kinh":              {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "trẅ kinh":              {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "muộn kinh":             {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "muon kinh":             {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "chậm kinh":             {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "cham kinh":             {"en": "Delayed menstruation",      "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "mất kinh":              {"en": "Amenorrhea",                "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "mat kinh":              {"en": "Amenorrhea",                "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "kinh nguyệt không đều": {"en": "Irregular menstruation",   "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "đau bụng kinh":         {"en": "Dysmenorrhea",              "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "dau bung kinh":         {"en": "Dysmenorrhea",              "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "ra máu âm đạo":         {"en": "Abnormal uterine bleeding", "domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "khí hư bất thường":     {"en": "Abnormal vaginal discharge","domain": "OBGYN", "icd_prefixes": ["N", "O"]},
    "đau vùng chậu":         {"en": "Pelvic pain",              "domain": "OBGYN", "icd_prefixes": ["N", "O", "R"]},

    # ── CARDIOLOGY ──────────────────────────────────────────────────────────
    "đau ngực":              {"en": "Chest pain",               "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "dau nguc":              {"en": "Chest pain",               "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "đau ngực trái":         {"en": "Left-sided chest pain",    "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "dau nguc trai":         {"en": "Left-sided chest pain",    "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "tức ngực":              {"en": "Chest tightness",          "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "đau thắt ngực":         {"en": "Angina pectoris",          "domain": "CARDIOLOGY", "icd_prefixes": ["I"]},
    "hồi hộp":               {"en": "Palpitations",             "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "tim đập nhanh":         {"en": "Tachycardia",              "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},
    "ngất":                  {"en": "Syncope",                  "domain": "CARDIOLOGY", "icd_prefixes": ["R"]},
    "vã mồ hôi":             {"en": "Diaphoresis",              "domain": "CARDIOLOGY", "icd_prefixes": ["I", "R"]},

    # ── NEUROLOGY ───────────────────────────────────────────────────────────
    "cứng cổ":               {"en": "Neck stiffness",           "domain": "NEUROLOGY", "icd_prefixes": ["G", "A", "B"]},
    "cung co":               {"en": "Neck stiffness",           "domain": "NEUROLOGY", "icd_prefixes": ["G", "A", "B"]},
    "sợ ánh sáng":           {"en": "Photophobia",              "domain": "NEUROLOGY", "icd_prefixes": ["G", "H"]},
    "đau đầu dữ dội":        {"en": "Severe headache",          "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "co giật":               {"en": "Seizure",                  "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "co giat":               {"en": "Seizure",                  "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "động kinh":             {"en": "Epilepsy",                 "domain": "NEUROLOGY", "icd_prefixes": ["G"]},
    "dong kinh":             {"en": "Epilepsy",                 "domain": "NEUROLOGY", "icd_prefixes": ["G"]},
    "liệt nửa người":        {"en": "Hemiparesis",              "domain": "NEUROLOGY", "icd_prefixes": ["G", "I"]},
    "nói ngọng":             {"en": "Dysarthria",               "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "noi ngong":             {"en": "Dysarthria",               "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "đi loạng":              {"en": "Ataxia",                   "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "di loang":              {"en": "Ataxia",                   "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "loạng choạng":          {"en": "Gait ataxia",              "domain": "NEUROLOGY", "icd_prefixes": ["G", "R"]},
    "mất thăng bằng":        {"en": "Loss of balance",          "domain": "NEUROLOGY", "icd_prefixes": ["G", "H", "R"]},

    # ── GENERAL / INFECTION ─────────────────────────────────────────────────
    "sốt cao":               {"en": "High fever",               "domain": "GENERAL",   "icd_prefixes": ["A", "B", "R"]},
    "sot cao":               {"en": "High fever",               "domain": "GENERAL",   "icd_prefixes": ["A", "B", "R"]},
    "sốt":                   {"en": "Fever",                    "domain": "GENERAL",   "icd_prefixes": ["A", "B", "R"]},
    "mệt mỏi":               {"en": "Fatigue",                  "domain": "GENERAL",   "icd_prefixes": ["R", "A", "B"]},

    # ── RESPIRATORY ─────────────────────────────────────────────────────────
    "khó thở":               {"en": "Shortness of breath",      "domain": "RESPIRATORY","icd_prefixes": ["J", "R", "I"]},
    "kho tho":               {"en": "Shortness of breath",      "domain": "RESPIRATORY","icd_prefixes": ["J", "R", "I"]},
    "ho":                    {"en": "Cough",                    "domain": "RESPIRATORY","icd_prefixes": ["J", "R", "A"]},
    "ho kéo dài":            {"en": "Persistent cough",         "domain": "RESPIRATORY","icd_prefixes": ["J", "A"]},

    # ── URINARY ─────────────────────────────────────────────────────────────
    "tiểu buốt":             {"en": "Dysuria",                  "domain": "UROLOGY",   "icd_prefixes": ["N"]},
    "tieu buot":             {"en": "Dysuria",                  "domain": "UROLOGY",   "icd_prefixes": ["N"]},
    "tiểu gắt":              {"en": "Urinary urgency",          "domain": "UROLOGY",   "icd_prefixes": ["N"]},
    "nước tiểu đục":         {"en": "Cloudy urine",             "domain": "UROLOGY",   "icd_prefixes": ["N", "R"]},
    "tiểu ra máu":           {"en": "Hematuria",                "domain": "UROLOGY",   "icd_prefixes": ["N", "R"]},

    # ── GI ──────────────────────────────────────────────────────────────────
    "đau bụng":              {"en": "Abdominal pain",           "domain": "GI",        "icd_prefixes": ["K", "R"]},
    "dau bung":              {"en": "Abdominal pain",           "domain": "GI",        "icd_prefixes": ["K", "R"]},
    "buồn nôn":              {"en": "Nausea",                   "domain": "GI",        "icd_prefixes": ["R", "K"]},
    "tiêu chảy":             {"en": "Diarrhea",                 "domain": "GI",        "icd_prefixes": ["K", "A"]},
    "táo bón":               {"en": "Constipation",             "domain": "GI",        "icd_prefixes": ["K"]},
}

# ── Layer 2: MeSH-subset whitelist (curated for VN clinical use) ─────────────
# Chỉ các thuật ngữ này mới được phép ra kết quả cuối cùng.
MESH_WHITELIST: frozenset[str] = frozenset([
    # OB/GYN
    "delayed menstruation", "amenorrhea", "dysmenorrhea", "irregular menstruation",
    "abnormal uterine bleeding", "pelvic pain", "abnormal vaginal discharge",
    "menorrhagia", "metrorrhagia", "oligomenorrhea",
    # Cardiology
    "chest pain", "left-sided chest pain", "angina pectoris", "chest tightness",
    "palpitations", "tachycardia", "syncope", "diaphoresis", "hypertension",
    "myocardial infarction", "heart failure",
    # Neurology
    "headache", "severe headache", "migraine", "neck stiffness", "photophobia",
    "seizure", "epilepsy", "hemiparesis", "hemiplegia", "dysarthria",
    "ataxia", "gait ataxia", "loss of balance", "vertigo", "dizziness",
    "facial droop", "sudden confusion", "meningitis",
    # General/Infection
    "fever", "high fever", "fatigue", "weight loss", "chills", "myalgia",
    "lymphadenopathy", "sepsis",
    # Respiratory
    "cough", "persistent cough", "shortness of breath", "dyspnea",
    "wheezing", "hemoptysis", "tachypnea", "pleuritic chest pain",
    # Urinary
    "dysuria", "urinary urgency", "hematuria", "cloudy urine",
    "urinary frequency", "urinary retention", "nocturia",
    # GI
    "abdominal pain", "nausea", "vomiting", "diarrhea", "constipation",
    "heartburn", "acid reflux", "epigastric pain", "bloating",
    "blood in stool", "melena",
    # Skin
    "rash", "urticaria", "pruritus", "jaundice",
    # MSK
    "joint pain", "back pain", "myalgia", "arthralgia",
    # ENT
    "sore throat", "hoarseness", "tinnitus", "hearing loss",
    # Alcohol/Tox
    "alcohol intoxication",
])

# ── Layer 3: Domain → ICD chapter map ───────────────────────────────────────
DOMAIN_ICD_MAP: dict[str, frozenset[str]] = {
    "OBGYN":       frozenset(["N", "O"]),
    "CARDIOLOGY":  frozenset(["I", "R"]),
    "NEUROLOGY":   frozenset(["G", "R", "I", "A", "B"]),
    "RESPIRATORY": frozenset(["J", "R", "I", "A", "B"]),
    "UROLOGY":     frozenset(["N", "R"]),
    "GI":          frozenset(["K", "R", "A", "B"]),
    "GENERAL":     frozenset(["A", "B", "R", "Z"]),
}
# R và Z luôn được phép (symptom codes + factors)
_UNIVERSAL_CHAPTERS: frozenset[str] = frozenset(["R", "Z"])


# ── Dataclass for gatekeeper result ─────────────────────────────────────────
@dataclass
class GateResult:
    passed: bool
    canonical_en: str = ""
    domain: str = ""
    allowed_chapters: frozenset[str] = field(default_factory=frozenset)
    reject_reason: str = ""
    layer_stopped: int = 0   # 1-4, 0 = all passed


# ── MedicalGatekeeper ────────────────────────────────────────────────────────

class MedicalGatekeeper:
    """
    4-layer Medical Gatekeeper — V1.0

    Usage:
        gate = MedicalGatekeeper()
        result = gate.validate(symptom_text, icd_code, icd_description, sim_score)
        if not result.passed:
            # REJECT — use result.reject_reason
    """

    # Pre-compiled normalization patterns
    _CLEAN = re.compile(r"[\?\ufffd\u0000-\u001F]")
    _SPACE = re.compile(r"\s{2,}")

    # Encoding corruption patterns: map broken → canonical Vietnamese
    _ENCODING_FIX: list[tuple[re.Pattern, str]] = [
        (re.compile(r"tr[e\?]{1,2}\s*kinh", re.I), "trễ kinh"),
        (re.compile(r"mu[o\?]{1,2}n\s*kinh", re.I), "muộn kinh"),
        (re.compile(r"ch[a\?]{1,2}m\s*kinh", re.I), "chậm kinh"),
        (re.compile(r"d[o\?]{1,2}ng\s*kinh", re.I), "động kinh"),
        (re.compile(r"kh[o\?]{1,2}\s*th[o\?]{1,2}", re.I), "khó thở"),
        (re.compile(r"d[a\?]{1,2}u\s*ng[u\?]{1,2}c", re.I), "đau ngực"),
    ]

    def normalize(self, text: str) -> str:
        """Layer 1a — fix encoding corruption then lowercase."""
        t = str(text or "").strip()
        # Fix known corrupt patterns first
        for pattern, replacement in self._ENCODING_FIX:
            t = pattern.sub(replacement, t)
        # Strip non-printable / replacement chars
        t = self._CLEAN.sub(" ", t)
        t = self._SPACE.sub(" ", t).strip().lower()
        return t

    def canonical_lookup(self, symptom_lower: str) -> tuple[str, str, frozenset[str]] | None:
        """
        Layer 1b — canonical mapping: longest-key-first match.
        Returns (canonical_en, domain, allowed_chapters) or None.
        """
        # Try exact match first (fastest)
        if symptom_lower in CANONICAL_MAP:
            entry = CANONICAL_MAP[symptom_lower]
            return entry["en"], entry["domain"], frozenset(entry["icd_prefixes"]) | _UNIVERSAL_CHAPTERS

        # Substring match — longest key wins
        keys_sorted = sorted(CANONICAL_MAP.keys(), key=len, reverse=True)
        for key in keys_sorted:
            if key in symptom_lower:
                entry = CANONICAL_MAP[key]
                return entry["en"], entry["domain"], frozenset(entry["icd_prefixes"]) | _UNIVERSAL_CHAPTERS

        return None

    def validate_mesh(self, canonical_en: str) -> bool:
        """Layer 2 — check canonical term against MeSH whitelist."""
        term_lower = canonical_en.lower()
        # Exact or prefix match
        if term_lower in MESH_WHITELIST:
            return True
        return any(term_lower.startswith(w) or w in term_lower for w in MESH_WHITELIST)

    def validate_domain(
        self,
        icd_code: str,
        allowed_chapters: frozenset[str],
        domain: str,
    ) -> tuple[bool, str]:
        """Layer 3 — ICD chapter must be in allowed set for this domain."""
        if not icd_code:
            return False, "ICD code rỗng"
        chap = icd_code[0].upper()
        if chap in allowed_chapters:
            return True, "OK"
        return (
            False,
            f"SAI MIỀN: ICD {icd_code} chương '{chap}' không thuộc miền {domain} "
            f"(cho phép: {sorted(allowed_chapters)})",
        )

    def get_threshold(self, domain: str, is_red_flag: bool = False) -> float:
        """Layer 4 — adaptive threshold per domain."""
        if is_red_flag:
            return 0.33
        # OB/GYN and neurology tend to have lower embedding overlap with short ICD descriptions
        if domain in ("OBGYN", "NEUROLOGY"):
            return 0.35
        return 0.38

    def validate(
        self,
        symptom: str,
        icd_code: str,
        icd_description: str,
        sim_score: float,
        is_red_flag: bool = False,
    ) -> GateResult:
        """
        Run all 4 layers. Returns GateResult.
        Short-circuit: stop at first failed layer.
        """
        # ── Layer 1: Canonical mapping ──────────────────────────────────────
        norm = self.normalize(symptom)
        lookup = self.canonical_lookup(norm)

        canonical_en = ""
        domain = "GENERAL"
        allowed_chapters: frozenset[str] = _UNIVERSAL_CHAPTERS

        if lookup:
            canonical_en, domain, allowed_chapters = lookup
        else:
            # No canonical found — allow but mark as unvalidated domain
            canonical_en = norm
            domain = "UNKNOWN"
            allowed_chapters = frozenset(["A","B","G","I","J","K","N","O","R","Z"])

        # ── Layer 2: MeSH whitelist ──────────────────────────────────────────
        if canonical_en and not self.validate_mesh(canonical_en):
            return GateResult(
                passed=False,
                canonical_en=canonical_en,
                domain=domain,
                allowed_chapters=allowed_chapters,
                reject_reason=f"Lỗi thuật ngữ: '{canonical_en}' không tìm thấy thực thể y khoa tương ứng trong từ điển MeSH.",
                layer_stopped=2,
            )

        # ── Layer 3: Domain / chapter lock ──────────────────────────────────
        chap_ok, chap_reason = self.validate_domain(icd_code, allowed_chapters, domain)
        if not chap_ok:
            return GateResult(
                passed=False,
                canonical_en=canonical_en,
                domain=domain,
                allowed_chapters=allowed_chapters,
                reject_reason=f"SAI MIỀN CHUYÊN KHOA: {chap_reason} — Không thể đoán mò!",
                layer_stopped=3,
            )

        # ── Layer 4: Reverse similarity threshold ───────────────────────────
        threshold = self.get_threshold(domain, is_red_flag)
        if sim_score < threshold:
            return GateResult(
                passed=False,
                canonical_en=canonical_en,
                domain=domain,
                allowed_chapters=allowed_chapters,
                reject_reason=(
                    f"ĐỘ TIN CẬY THẤP: sim={sim_score:.3f} < {threshold} "
                    f"(domain={domain}) — Mời nhập thêm dữ liệu."
                ),
                layer_stopped=4,
            )

        return GateResult(
            passed=True,
            canonical_en=canonical_en,
            domain=domain,
            allowed_chapters=allowed_chapters,
        )


# ── Module-level singleton ───────────────────────────────────────────────────
_gatekeeper = MedicalGatekeeper()


def gate_check(
    symptom: str,
    icd_code: str,
    icd_description: str,
    sim_score: float,
    is_red_flag: bool = False,
) -> GateResult:
    """Convenience wrapper — sử dụng singleton gatekeeper."""
    return _gatekeeper.validate(symptom, icd_code, icd_description, sim_score, is_red_flag)
