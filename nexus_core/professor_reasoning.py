"""
professor_reasoning.py — Clinical Reasoning Engine (V9.1)
==========================================================
Role: Associate Professor (Phó Giáo sư) level differential diagnosis reasoner.

Responsibilities:
  1. Red Flag Protocol   — elevate life-threatening diagnoses regardless of base score
  2. Pathognomonic Boost — multiply confidence for "gold-standard" symptom pairs
  3. Differential Logic  — generate exclusion questions for top-3 candidates
  4. Bayesian Update     — re-compute probabilities from doctor Yes/No answers
  5. Weight Matrix       — NumPy vectorized score adjustment; latency < 2 ms

All knowledge is stored as module-level constants (built once at import time).
No Ollama calls — pure Python + NumPy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Base — built once at import time
# ─────────────────────────────────────────────────────────────────────────────

# RED FLAG REGISTRY
# key   = ICD-10 prefix (first 3 chars)
# value = {name, urgency, trigger_kw (frozenset), reason}
_RED_FLAGS: dict[str, dict[str, Any]] = {
    "I21": {
        "name": "Nhồi máu cơ tim cấp (STEMI/NSTEMI)",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["đau ngực", "chest pain", "bức rức ngực", "tức ngực", "đau thắt ngực"]),
        "reason": "Cần ECG và troponin ngay. Mỗi phút delay = 2M tế bào cơ tim chết.",
    },
    "I26": {
        "name": "Thuyên tắc phổi (Pulmonary Embolism)",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["khó thở đột ngột", "đau ngực", "ho ra máu", "phù chân 1 bên"]),
        "reason": "Cần CT Angiography phổi ngay. Tỉ lệ tử vong > 30% nếu trễ.",
    },
    "G03": {
        "name": "Viêm màng não mủ (Bacterial Meningitis)",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["sốt cao", "cứng cổ", "đau đầu", "neck stiffness", "high fever"]),
        "reason": "Tam chứng: Sốt + Cứng cổ + Rối loạn tri giác. Cần chọc dịch não tủy ngay.",
    },
    "I60": {
        "name": "Xuất huyết dưới nhện (Subarachnoid Hemorrhage)",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["đau đầu dữ dội đột ngột", "thunderclap headache", "đau đầu tệ nhất đời"]),
        "reason": "'Thunderclap headache' — đau đầu dữ dội đột ngột là dấu hiệu vỡ phình động mạch.",
    },
    "A41": {
        "name": "Nhiễm khuẩn huyết — Sepsis",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["sốt cao", "lơ mơ", "tụt huyết áp", "high fever", "ớn lạnh"]),
        "reason": "Sepsis bundle: cấy máu + kháng sinh TM + bù dịch trong 1 giờ (Hour-1 Bundle).",
    },
    "I63": {
        "name": "Nhồi máu não (Ischemic Stroke)",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["liệt nửa người", "nói khó", "méo miệng", "yếu tay chân đột ngột", "stroke"]),
        "reason": "FAST: Face-Arm-Speech-Time. Cửa sổ tPA ≤ 4.5 giờ. Mỗi giây = 32 000 neuron.",
    },
    "J96": {
        "name": "Suy hô hấp cấp (Acute Respiratory Failure)",
        "urgency": "CRITICAL",
        "trigger_kw": frozenset(["khó thở nặng", "tím tái", "SpO2 thấp", "không thở được"]),
        "reason": "SpO2 < 90%: đặt NKQ ngay. Không chờ kết quả xét nghiệm.",
    },
    "K92": {
        "name": "Xuất huyết tiêu hóa trên (Upper GI Bleed)",
        "urgency": "HIGH",
        "trigger_kw": frozenset(["nôn ra máu", "đi ngoài phân đen", "hematemesis", "melena"]),
        "reason": "Nội soi cấp cứu trong 24h. Truyền máu nếu Hb < 7 g/dL.",
    },
    "N17": {
        "name": "Suy thận cấp (AKI)",
        "urgency": "HIGH",
        "trigger_kw": frozenset(["thiểu niệu", "vô niệu", "phù toàn thân", "oliguria"]),
        "reason": "Creatinine tăng ≥ 1.5× baseline trong 7 ngày. Kiểm tra điện giải khẩn.",
    },
}

# PATHOGNOMONIC PAIRS
# List of (required_kw_subset, min_match_count, boost_factor, target_icd_prefixes, pattern_name)
# boost_factor multiplies the base score for matching candidates
_PATHOGNOMONIC: list[dict[str, Any]] = [
    {
        "name": "Meningitis Triad",
        "keywords": frozenset(["sốt cao", "cứng cổ", "đau đầu"]),
        "min_matches": 2,
        "boost": 3.0,
        "targets": frozenset(["G03", "G04", "A87", "G00"]),
        "note": "Sốt + Cứng cổ → Viêm màng não cho đến khi loại trừ.",
    },
    {
        "name": "Acute MI Pattern",
        "keywords": frozenset(["đau ngực", "mồ hôi lạnh", "buồn nôn", "tức ngực"]),
        "min_matches": 2,
        "boost": 2.5,
        "targets": frozenset(["I21", "I22", "I20"]),
        "note": "Đau ngực + Mồ hôi lạnh → phải loại trừ ACS trước.",
    },
    {
        "name": "Subarachnoid Hemorrhage",
        "keywords": frozenset(["đau đầu dữ dội đột ngột", "cứng cổ", "nôn vọt"]),
        "min_matches": 2,
        "boost": 2.8,
        "targets": frozenset(["I60", "I61"]),
        "note": "'Thunderclap + Neck stiffness' → SAH cho đến khi CT-scan bác bỏ.",
    },
    {
        "name": "Sepsis Red Flag",
        "keywords": frozenset(["sốt cao", "ớn lạnh", "lơ mơ", "mạch nhanh"]),
        "min_matches": 2,
        "boost": 2.0,
        "targets": frozenset(["A41", "A40"]),
        "note": "SOFA score ≥ 2 + nguồn nhiễm trùng → Sepsis.",
    },
    {
        "name": "Pulmonary Embolism",
        "keywords": frozenset(["khó thở đột ngột", "đau ngực", "phù chân", "ho ra máu"]),
        "min_matches": 2,
        "boost": 2.2,
        "targets": frozenset(["I26", "I27"]),
        "note": "Wells Score ≥ 4 → nguy cơ cao PE. CT Angiography ngay.",
    },
    {
        "name": "Upper UTI (Pyelonephritis)",
        "keywords": frozenset(["tiểu buốt", "tiểu giắt", "sốt cao", "đau hông lưng"]),
        "min_matches": 3,
        "boost": 1.8,
        "targets": frozenset(["N10", "N11", "N12"]),
        "note": "Tiểu buốt + Sốt cao + Đau hông lưng → nghi viêm thận-bể thận.",
    },
]

# DIFFERENTIAL EXCLUSION HINTS
# ICD prefix → (expected_hallmark_vn, exclusion_question)
_EXCLUSION: dict[str, tuple[str, str]] = {
    "I21": (
        "đau thắt ngực điển hình lan ra cánh tay trái / hàm dưới",
        "Nếu là nhồi máu cơ tim, tại sao không có đau thắt ngực điển hình lan ra vai trái hoặc hàm?"
    ),
    "I22": (
        "đau thắt ngực tái phát sau MI cũ",
        "Nếu là nhồi máu cơ tim tái phát, đã có tiền sử MI trước đó chưa?"
    ),
    "I26": (
        "khó thở đột ngột không rõ nguyên nhân, đau kiểu màng phổi",
        "Nếu là thuyên tắc phổi, tại sao không có khó thở xảy ra đột ngột khi nghỉ ngơi?"
    ),
    "G03": (
        "tam chứng: sốt cao + cứng cổ + rối loạn tri giác (Kernig/Brudzinski dương tính)",
        "Nếu là viêm màng não mủ, tại sao không có tam chứng cổ điển đầy đủ?"
    ),
    "G00": (
        "cứng cổ + sốt + thay đổi tri giác",
        "Nếu là viêm màng não vi khuẩn, tại sao không có cứng cổ rõ ràng khi thăm khám?"
    ),
    "I60": (
        "đau đầu kiểu 'sét đánh' — khởi phát đột ngột, dữ dội nhất trong đời",
        "Nếu là xuất huyết dưới nhện, đau đầu có khởi phát đột ngột cực kỳ dữ dội không?"
    ),
    "A41": (
        "huyết áp tụt, nhịp tim nhanh, lơ mơ — dấu hiệu rối loạn huyết động",
        "Nếu là nhiễm khuẩn huyết, tại sao không có dấu hiệu rối loạn huyết động (tụt HA, mạch nhanh)?"
    ),
    "N10": (
        "đau hông lưng 1 bên, sốt cao, tiểu buốt — gõ góc sườn lưng đau",
        "Nếu là viêm thận-bể thận, tại sao không có đau khi gõ góc sườn lưng (CVA tenderness)?"
    ),
    "N30": (
        "tiểu buốt + tiểu giắt + nước tiểu đục — không kèm sốt cao",
        "Nếu là viêm bàng quang đơn thuần, tại sao có sốt cao (gợi ý bệnh lan lên thận)?"
    ),
    "J18": (
        "ho có đờm màu gỉ sắt/xanh + sốt + đau ngực khi thở sâu",
        "Nếu là viêm phổi, tại sao không có hội chứng đông đặc (gõ đục, ran nổ) trên lâm sàng?"
    ),
    "J45": (
        "khò khè lan tỏa 2 bên phổi, cải thiện sau giãn phế quản",
        "Nếu là hen phế quản, tại sao không có khò khè 2 bên phổi hoặc tiền sử dị ứng?"
    ),
    "K35": (
        "đau hố chậu phải + sốt + buồn nôn — điểm McBurney dương tính",
        "Nếu là viêm ruột thừa, tại sao không có đau điểm McBurney điển hình?"
    ),
    "K80": (
        "đau hạ sườn phải lan ra sau lưng sau bữa ăn nhiều mỡ",
        "Nếu là sỏi mật, tại sao không có đau colic mật điển hình sau bữa ăn?"
    ),
    "E11": (
        "khát nước, tiểu nhiều, sụt cân + tiền sử gia đình ĐTĐ",
        "Nếu là đái tháo đường type 2, tại sao không có tam chứng: khát-tiểu nhiều-sụt cân?"
    ),
    "I63": (
        "FAST: liệt mặt/tay/chân đột ngột + nói khó + khởi phát đột ngột",
        "Nếu là nhồi máu não, tại sao không có dấu hiệu thần kinh khu trú khởi phát đột ngột?"
    ),
}

# FEATURE EXTRACTION — symptom → feature index
_FEATURES: list[tuple[frozenset[str], str]] = [
    (frozenset(["sốt cao", "fever", "high fever"]),            "has_fever"),
    (frozenset(["cứng cổ", "neck stiffness", "stiff neck"]),   "has_neck_stiff"),
    (frozenset(["đau ngực", "chest pain", "tức ngực"]),        "has_chest_pain"),
    (frozenset(["khó thở", "dyspnea", "shortness of breath"]), "has_dyspnea"),
    (frozenset(["tiểu buốt", "tiểu giắt", "dysuria"]),         "has_dysuria"),
    (frozenset(["đau đầu", "headache", "nhức đầu"]),            "has_headache"),
    (frozenset(["nôn", "vomit", "nausea", "buồn nôn"]),        "has_nausea"),
    (frozenset(["phát ban", "rash", "ban xuất huyết"]),         "has_rash"),
    (frozenset(["lơ mơ", "confusion", "altered consciousness"]),"has_altered_ms"),
    (frozenset(["mồ hôi lạnh", "diaphoresis", "cold sweat"]),  "has_diaphoresis"),
]

# ICD prefix → feature weight vector (same order as _FEATURES)
# w[i] > 1.0 means "this feature boosts this code"; < 1.0 means "mismatch penalty"
_WEIGHT_MATRIX: dict[str, list[float]] = {
    #              fever  neck  chest dyspn dysur head  naus  rash  altms diap
    "G03": [1.8,   2.5,  0.8,  0.8,  0.3,  1.5,  1.2,  1.1,  1.6,  0.8],
    "G00": [1.8,   2.5,  0.8,  0.8,  0.3,  1.5,  1.2,  1.0,  1.6,  0.8],
    "I21": [0.9,   0.8,  2.5,  1.4,  0.4,  0.8,  1.3,  0.6,  0.8,  2.2],
    "I26": [0.9,   0.7,  1.6,  2.5,  0.4,  0.8,  1.1,  0.6,  0.7,  1.2],
    "I60": [1.0,   1.8,  0.7,  0.7,  0.3,  2.8,  1.5,  0.6,  1.4,  0.8],
    "A41": [2.0,   0.9,  0.8,  1.2,  0.5,  1.0,  1.2,  1.2,  2.0,  1.3],
    "N10": [1.8,   0.6,  0.6,  0.6,  1.8,  0.8,  1.0,  0.6,  0.7,  0.7],
    "N30": [0.8,   0.6,  0.6,  0.6,  2.2,  0.7,  0.9,  0.6,  0.5,  0.6],
    "J18": [1.6,   0.7,  1.1,  1.5,  0.5,  0.9,  1.0,  0.8,  0.7,  0.8],
    "J45": [0.8,   0.6,  0.8,  2.2,  0.5,  0.8,  0.9,  1.2,  0.5,  0.6],
    "K35": [1.5,   0.6,  0.7,  0.7,  0.5,  0.9,  1.4,  0.6,  0.8,  0.7],
    "I63": [0.8,   0.8,  0.7,  0.8,  0.3,  1.2,  1.1,  0.6,  1.8,  0.8],
}
_DEFAULT_WEIGHTS = [1.0] * len(_FEATURES)


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RedFlag:
    code: str
    name: str
    urgency: str          # "CRITICAL" | "HIGH"
    reason: str
    triggered_by: list[str] = field(default_factory=list)


@dataclass
class PathognomicBoost:
    pattern_name: str
    matched_keywords: list[str]
    boost_factor: float
    boosted_codes: list[str]
    note: str


@dataclass
class DifferentialExclusion:
    code: str
    name: str
    expected_hallmark: str
    exclusion_question: str   # "Nếu là X, tại sao không có Y?"


@dataclass
class AdjustedItem:
    code: str
    description: str
    base_prob: float          # original softmax prob (%)
    adjusted_prob: float      # after weight matrix + boost (%)
    expert_label: str         # "🔴 LOẠI TRỪ KHẨN" / "🟠 ĐỀ NGHỊ" / "🟢 THEO DÕI"
    is_red_flag: bool = False


@dataclass
class ExpertInsight:
    """Full output of ProfessorReasoning.analyze()."""
    adjusted_items: list[AdjustedItem]
    red_flags: list[RedFlag]
    pathognomonic_boosts: list[PathognomicBoost]
    differential_exclusions: list[DifferentialExclusion]
    expert_summary: str
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjusted_items": [
                {
                    "code": it.code,
                    "description": it.description,
                    "base_prob": round(it.base_prob, 1),
                    "adjusted_prob": round(it.adjusted_prob, 1),
                    "expert_label": it.expert_label,
                    "is_red_flag": it.is_red_flag,
                }
                for it in self.adjusted_items
            ],
            "red_flags": [
                {
                    "code": rf.code,
                    "name": rf.name,
                    "urgency": rf.urgency,
                    "reason": rf.reason,
                    "triggered_by": rf.triggered_by,
                }
                for rf in self.red_flags
            ],
            "pathognomonic_boosts": [
                {
                    "pattern_name": pb.pattern_name,
                    "matched_keywords": pb.matched_keywords,
                    "boost_factor": pb.boost_factor,
                    "boosted_codes": pb.boosted_codes,
                    "note": pb.note,
                }
                for pb in self.pathognomonic_boosts
            ],
            "differential_exclusions": [
                {
                    "code": de.code,
                    "name": de.name,
                    "expected_hallmark": de.expected_hallmark,
                    "exclusion_question": de.exclusion_question,
                }
                for de in self.differential_exclusions
            ],
            "expert_summary": self.expert_summary,
            "latency_ms": round(self.latency_ms, 3),
        }


# ─────────────────────────────────────────────────────────────────────────────
# ProfessorReasoning
# ─────────────────────────────────────────────────────────────────────────────

class ProfessorReasoning:
    """
    Associate-Professor level clinical reasoner.
    All computation is pure Python + NumPy — no I/O, no Ollama calls.
    Typical latency: 0.3 – 1.5 ms for 5 candidates.
    """

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def analyze(
        symptoms: str,
        candidates: list[dict[str, Any]],
        base_probs: list[float],        # 0-100 % probabilities (same order as candidates)
    ) -> ExpertInsight:
        """
        Full reasoning pipeline.

        Args:
            symptoms:    Raw Vietnamese symptom string.
            candidates:  List of {code, description, score} dicts (up to 5).
            base_probs:  Corresponding probabilities in 0-100 range (softmax output).

        Returns:
            ExpertInsight with adjusted probs, red flags, boosts, exclusions.
        """
        import time
        t0 = time.perf_counter()

        text_lower = (symptoms or "").lower()
        n = len(candidates)
        if n == 0:
            return ExpertInsight([], [], [], [], "Không có ứng viên để phân tích.")

        codes = [str(c.get("code") or "")[:3] for c in candidates]  # 3-char prefix
        full_codes = [str(c.get("code") or "") for c in candidates]
        descs  = [str(c.get("description") or "") for c in candidates]
        probs  = np.asarray(base_probs[:n], dtype=np.float64)

        # ── Step 1: Extract feature vector ───────────────────────────────────
        feat_vec = ProfessorReasoning._feature_vector(text_lower)

        # ── Step 2: Weight matrix adjustment ─────────────────────────────────
        weight_vec = ProfessorReasoning._compute_weight_vector(codes, feat_vec)
        probs_adj = probs * weight_vec          # element-wise, O(n × F) where n≤5
        probs_adj = np.clip(probs_adj, 0.1, 100.0)

        # ── Step 3: Red flags ─────────────────────────────────────────────────
        red_flags = ProfessorReasoning._detect_red_flags(text_lower, codes, full_codes)

        # Inject red-flag boost: any candidate that IS a red flag gets floor of 40 %
        for i, code in enumerate(codes):
            if any(rf.code == code or rf.code == full_codes[i][:3] for rf in red_flags):
                probs_adj[i] = max(probs_adj[i], 40.0)

        # ── Step 4: Pathognomonic boost ───────────────────────────────────────
        boosts, probs_adj = ProfessorReasoning._apply_pathognomonic(
            text_lower, codes, full_codes, probs_adj
        )

        # ── Step 5: Re-normalise to sum 100 ──────────────────────────────────
        total = probs_adj.sum()
        if total > 0:
            probs_adj = probs_adj / total * 100.0

        # ── Step 6: Differential exclusions (top 3) ───────────────────────────
        sorted_idx = np.argsort(probs_adj)[::-1]
        exclusions = ProfessorReasoning._build_exclusions(
            sorted_idx[:3], codes, full_codes, descs
        )

        # ── Step 7: Labelled adjusted items ──────────────────────────────────
        rf_code_set = {rf.code for rf in red_flags}
        adj_items: list[AdjustedItem] = []
        for i, idx in enumerate(sorted_idx):
            code3 = codes[idx]
            fc    = full_codes[idx]
            p_adj = float(probs_adj[idx])
            label = ProfessorReasoning._expert_label(p_adj, code3 in rf_code_set or fc[:3] in rf_code_set)
            adj_items.append(AdjustedItem(
                code=fc,
                description=descs[idx],
                base_prob=float(probs[idx]),
                adjusted_prob=round(p_adj, 1),
                expert_label=label,
                is_red_flag=(code3 in rf_code_set or fc[:3] in rf_code_set),
            ))

        # ── Step 8: Expert summary ────────────────────────────────────────────
        summary = ProfessorReasoning._build_summary(
            symptoms, adj_items, red_flags, boosts
        )

        elapsed = (time.perf_counter() - t0) * 1000
        return ExpertInsight(
            adjusted_items=adj_items,
            red_flags=red_flags,
            pathognomonic_boosts=boosts,
            differential_exclusions=exclusions,
            expert_summary=summary,
            latency_ms=elapsed,
        )

    @staticmethod
    def bayesian_update(
        probs: list[float],      # current probabilities 0-100 (sum=100)
        codes: list[str],        # ICD codes parallel to probs
        effects: dict[str, float],  # {code: likelihood_ratio} for a Yes/No answer
    ) -> list[float]:
        """
        Apply Bayesian update given doctor's answer effect.
        new_prob_i ∝ old_prob_i × effects.get(code_i, 1.0)
        Then re-normalise to 100 %.
        Fully vectorized, O(n). Used by frontend but also exposed here for tests.
        """
        p = np.asarray(probs, dtype=np.float64)
        lr = np.array([effects.get(c[:3], effects.get(c, 1.0)) for c in codes], dtype=np.float64)
        p_new = p * lr
        total = p_new.sum()
        if total <= 0:
            return probs
        return (p_new / total * 100.0).tolist()

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _feature_vector(text_lower: str) -> np.ndarray:
        """Extract binary feature vector from symptom text.  O(F×K) ≈ O(100)."""
        vec = np.zeros(len(_FEATURES), dtype=np.float64)
        for i, (kw_set, _) in enumerate(_FEATURES):
            if any(k in text_lower for k in kw_set):
                vec[i] = 1.0
        return vec

    @staticmethod
    def _compute_weight_vector(codes3: list[str], feat_vec: np.ndarray) -> np.ndarray:
        """
        For each candidate, compute a scalar weight from its row in _WEIGHT_MATRIX.
        weight_i = dot(W[code_i], feat_vec) / (feat_vec.sum() + 1)
        Clipped to [0.5, 3.0] to avoid extreme swings.
        O(n × F) where n ≤ 5, F = 10 → ≈ 50 ops.
        """
        n = len(codes3)
        weights = np.ones(n, dtype=np.float64)
        denom = float(feat_vec.sum()) + 1.0
        for i, code3 in enumerate(codes3):
            row = _WEIGHT_MATRIX.get(code3, _DEFAULT_WEIGHTS)
            w_arr = np.asarray(row, dtype=np.float64)
            # Weighted dot: features that are present contribute their weight
            score = float(np.dot(w_arr, feat_vec)) / denom
            weights[i] = np.clip(score, 0.5, 3.0) if feat_vec.sum() > 0 else 1.0
        return weights

    @staticmethod
    def _detect_red_flags(
        text_lower: str,
        codes3: list[str],
        full_codes: list[str],
    ) -> list[RedFlag]:
        flags: list[RedFlag] = []
        # Check candidates that ARE red-flag codes
        for i, c3 in enumerate(codes3):
            if c3 in _RED_FLAGS:
                rf_info = _RED_FLAGS[c3]
                triggered = [k for k in rf_info["trigger_kw"] if k in text_lower]
                flags.append(RedFlag(
                    code=full_codes[i],
                    name=rf_info["name"],
                    urgency=rf_info["urgency"],
                    reason=rf_info["reason"],
                    triggered_by=triggered,
                ))
        # Check if symptoms suggest a red-flag NOT in candidates (inject warning)
        existing_codes3 = set(codes3)
        for code3, rf_info in _RED_FLAGS.items():
            if code3 in existing_codes3:
                continue
            triggered = [k for k in rf_info["trigger_kw"] if k in text_lower]
            if len(triggered) >= 2:   # ≥ 2 trigger keywords present but code not in top-5
                flags.append(RedFlag(
                    code=code3,
                    name=rf_info["name"],
                    urgency=rf_info["urgency"],
                    reason=f"⚠️ Không nằm trong Top-5 nhưng triệu chứng gợi ý: {', '.join(triggered)}. "
                           + rf_info["reason"],
                    triggered_by=triggered,
                ))
        # Sort: CRITICAL first
        flags.sort(key=lambda r: 0 if r.urgency == "CRITICAL" else 1)
        return flags

    @staticmethod
    def _apply_pathognomonic(
        text_lower: str,
        codes3: list[str],
        full_codes: list[str],
        probs: np.ndarray,
    ) -> tuple[list[PathognomicBoost], np.ndarray]:
        boosts: list[PathognomicBoost] = []
        probs_out = probs.copy()
        for pat in _PATHOGNOMONIC:
            matched = [k for k in pat["keywords"] if k in text_lower]
            if len(matched) < pat["min_matches"]:
                continue
            targets: frozenset[str] = pat["targets"]
            boosted: list[str] = []
            for i, c3 in enumerate(codes3):
                if c3 in targets or full_codes[i][:3] in targets:
                    probs_out[i] = min(probs_out[i] * pat["boost"], 95.0)
                    boosted.append(full_codes[i])
            if boosted:
                boosts.append(PathognomicBoost(
                    pattern_name=pat["name"],
                    matched_keywords=matched,
                    boost_factor=pat["boost"],
                    boosted_codes=boosted,
                    note=pat["note"],
                ))
        return boosts, probs_out

    @staticmethod
    def _build_exclusions(
        top_idx: np.ndarray,
        codes3: list[str],
        full_codes: list[str],
        descs: list[str],
    ) -> list[DifferentialExclusion]:
        exclusions: list[DifferentialExclusion] = []
        for idx in top_idx:
            c3   = codes3[idx]
            fc   = full_codes[idx]
            hint = _EXCLUSION.get(c3) or _EXCLUSION.get(fc[:3])
            if hint:
                exclusions.append(DifferentialExclusion(
                    code=fc,
                    name=descs[idx],
                    expected_hallmark=hint[0],
                    exclusion_question=hint[1],
                ))
            else:
                exclusions.append(DifferentialExclusion(
                    code=fc,
                    name=descs[idx],
                    expected_hallmark="(không có dữ liệu đặc trưng)",
                    exclusion_question=f"Nếu là {descs[idx]}, triệu chứng điển hình nào đang vắng mặt?",
                ))
        return exclusions

    @staticmethod
    def _expert_label(prob: float, is_red_flag: bool) -> str:
        if is_red_flag and prob >= 30:
            return "🔴 LOẠI TRỪ KHẨN"
        if is_red_flag:
            return "🔴 CẦN XEM XÉT"
        if prob >= 60:
            return "🟠 CHẨN ĐOÁN CHÍNH"
        if prob >= 35:
            return "🟡 ĐỀ NGHỊ XEM XÉT"
        return "🟢 THEO DÕI"

    @staticmethod
    def _build_summary(
        symptoms: str,
        items: list[AdjustedItem],
        flags: list[RedFlag],
        boosts: list[PathognomicBoost],
    ) -> str:
        lines: list[str] = []

        if flags:
            lines.append("🚨 **CẢNH BÁO CHUYÊN GIA:**")
            for rf in flags[:3]:
                urg = "⛔ CRITICAL" if rf.urgency == "CRITICAL" else "⚠️ HIGH"
                lines.append(f"  {urg} — **{rf.name}**: {rf.reason}")

        if boosts:
            lines.append("\n🎯 **DẤU HIỆU ĐẶC TRƯNG (Pathognomonic):**")
            for b in boosts:
                kw_str = " + ".join(f'"{k}"' for k in b.matched_keywords[:3])
                lines.append(f"  {kw_str} → **{b.pattern_name}** (boost ×{b.boost_factor:.1f}). {b.note}")

        if items:
            lines.append("\n📊 **PHÂN TÍCH XÁC SUẤT SAU HIỆU CHỈNH:**")
            for it in items[:3]:
                lines.append(f"  {it.expert_label} **{it.code}** — {it.description}: "
                             f"{it.adjusted_prob:.1f}% (gốc: {it.base_prob:.1f}%)")

        if not lines:
            lines.append("Không phát hiện dấu hiệu cảnh báo đặc biệt. "
                        "Tiếp tục theo dõi theo phác đồ chuẩn.")

        return "\n".join(lines)
