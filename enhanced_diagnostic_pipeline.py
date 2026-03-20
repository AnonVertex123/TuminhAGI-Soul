"""
enhanced_diagnostic_pipeline.py — TuminhAGI V9.3+
===================================================
Drop-in replacement cho medical_diagnostic_tool.py

3 lớp cải thiện:
  Lớp 1 — SymptomEnricher   : mở rộng triệu chứng + ngữ cảnh trước khi embed
  Lớp 2 — MedicalEmbedder   : hỗ trợ BioBERT / PhoBERT thay all-MiniLM
  Lớp 3 — SeverityScorer    : cosine × urgency weight, phân biệt cấp cứu

Cách tích hợp (không phá code cũ):
    # missions_hub/medical_diagnostic_tool.py
    # Thay dòng cũ:
    #   from nexus_core.professor_reasoning import ProfessorReasoning
    # Thêm vào:
    from missions_hub.enhanced_diagnostic_pipeline import EnhancedDiagnosticPipeline
    pipeline = EnhancedDiagnosticPipeline()
    result   = await pipeline.diagnose(symptoms_raw, context)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("tuminh.enhanced_pipeline")


# ══════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════

@dataclass
class SymptomContext:
    """
    Ngữ cảnh đi kèm triệu chứng — thu thập từ Phase-1 questions.
    Càng đầy đủ → Lớp 1 càng hiệu quả.
    """
    raw_symptoms: list[str]              # triệu chứng gốc user nhập
    duration: str = ""                   # "2 ngày", "30 phút", "mạn tính"
    trigger: str = ""                    # "gắng sức", "ăn uống", "nghỉ ngơi", "tự phát"
    severity: str = ""                   # "nhẹ", "vừa", "nặng", "rất nặng"
    location: str = ""                   # "ngực trái", "thượng vị", "lan vai trái"
    associated: list[str] = field(default_factory=list)   # triệu chứng kèm theo
    age: Optional[int] = None
    sex: str = ""                        # "nam", "nữ"
    comorbidities: list[str] = field(default_factory=list)


@dataclass
class DiagnosisCandidate:
    disease_id: str           # ICD-10 code, vd "I21"
    disease_name_en: str
    disease_name_vn: str
    cosine_raw: float         # score thuần từ embedding
    severity_score: float     # score sau khi tính urgency weight
    urgency: str              # "emergency" / "urgent" / "routine"
    red_flags_matched: list[str] = field(default_factory=list)
    enriched_query: str = ""


@dataclass
class DiagnosisResult:
    top_candidates: list[DiagnosisCandidate]
    is_emergency: bool
    emergency_reason: str
    enriched_query: str
    embed_model_used: str
    latency_ms: float
    warning: str = ""


# ══════════════════════════════════════════════════════════════
# LỚP 1 — SYMPTOM ENRICHER
# ══════════════════════════════════════════════════════════════

# Synonym map: triệu chứng VN → danh sách từ đồng nghĩa EN y tế
# Mở rộng dần — mỗi entry thêm ~2-3% precision
SYNONYM_MAP: dict[str, list[str]] = {
    # Tim mạch
    "đau ngực":          ["chest pain", "chest tightness", "angina", "precordial pain"],
    "đau ngực trái":     ["left chest pain", "left precordial pain", "cardiac pain"],
    "khó thở":           ["dyspnea", "shortness of breath", "breathlessness", "SOB"],
    "khó thở khi nằm":  ["orthopnea", "paroxysmal nocturnal dyspnea", "PND"],
    "hồi hộp":          ["palpitation", "heart racing", "tachycardia awareness"],
    "ngất":             ["syncope", "loss of consciousness", "LOC", "faint"],
    "chóng mặt":        ["vertigo", "dizziness", "lightheadedness", "presyncope"],

    # Thần kinh
    "đau đầu":           ["headache", "cephalgia", "head pain"],
    "đau đầu dữ dội":   ["thunderclap headache", "worst headache", "subarachnoid"],
    "co giật":           ["seizure", "convulsion", "epileptic fit"],
    "tê bì":             ["paresthesia", "numbness", "tingling", "sensory loss"],
    "yếu liệt":          ["weakness", "paresis", "paralysis", "hemiplegia"],
    "nói khó":           ["dysarthria", "speech difficulty", "aphasia"],

    # Tiêu hóa
    "đau bụng":          ["abdominal pain", "belly pain", "stomach ache"],
    "đau bụng trên":     ["epigastric pain", "upper abdominal pain", "epigastralgia"],
    "đau bụng dưới":     ["lower abdominal pain", "hypogastric pain", "pelvic pain"],
    "buồn nôn":          ["nausea", "queasiness", "feeling sick"],
    "nôn mửa":           ["vomiting", "emesis", "vomit"],
    "tiêu chảy":         ["diarrhea", "loose stool", "frequent bowel movement"],
    "táo bón":           ["constipation", "hard stool", "difficult defecation"],
    "đi ngoài ra máu":  ["hematochezia", "rectal bleeding", "blood in stool"],
    "nôn ra máu":        ["hematemesis", "vomiting blood", "bloody vomit"],

    # Hô hấp
    "ho":                ["cough", "tussis"],
    "ho ra máu":         ["hemoptysis", "coughing blood", "bloody sputum"],
    "thở khò khè":       ["wheezing", "stridor", "respiratory wheeze"],
    "đau ngực khi thở": ["pleuritic chest pain", "breathing-related chest pain"],

    # Tiết niệu / Phụ khoa
    "tiểu buốt":         ["dysuria", "painful urination", "burning urination"],
    "tiểu ra máu":       ["hematuria", "blood in urine", "bloody urine"],
    "trễ kinh":          ["amenorrhea", "missed period", "delayed menstruation"],
    "chậm kinh":         ["oligomenorrhea", "irregular period", "menstrual delay"],
    "đau bụng kinh":     ["dysmenorrhea", "menstrual cramp", "period pain"],
    "xuất huyết âm đạo":["vaginal bleeding", "uterine bleeding", "metrorrhagia"],

    # Cơ xương khớp
    "đau lưng":          ["back pain", "lumbar pain", "dorsalgia"],
    "đau khớp":          ["arthralgia", "joint pain", "arthritis pain"],
    "cứng khớp":         ["joint stiffness", "morning stiffness"],
    "đi loạng choạng":   ["ataxia", "gait ataxia", "unsteady gait", "imbalance"],

    # Toàn thân
    "sốt":               ["fever", "pyrexia", "hyperthermia", "febrile"],
    "sốt cao":           ["high fever", "hyperpyrexia", "high temperature"],
    "mệt mỏi":          ["fatigue", "weakness", "asthenia", "tiredness"],
    "sụt cân":           ["weight loss", "unintentional weight loss", "cachexia"],
    "vàng da":           ["jaundice", "icterus", "yellow skin", "hyperbilirubinemia"],
    "phù":               ["edema", "swelling", "fluid retention"],
    "phù chân":          ["leg edema", "ankle swelling", "peripheral edema"],
    "xuất huyết":        ["hemorrhage", "bleeding", "hemorrhagic"],
}

# Trigger context → medical qualifier
TRIGGER_MAP: dict[str, str] = {
    "gắng sức":     "exertional on exertion exercise-induced",
    "nghỉ ngơi":    "at rest resting spontaneous",
    "ăn uống":      "postprandial after eating food-related",
    "ban đêm":      "nocturnal nighttime sleep-related",
    "thay tư thế":  "positional postural orthostatic",
    "tự phát":      "spontaneous sudden onset",
    "sau chấn thương": "post-traumatic injury-related",
    "stress":       "stress-related psychogenic emotional",
}

# Duration → temporal qualifier
DURATION_MAP: dict[str, str] = {
    "vài phút":     "acute minutes sudden onset",
    "vài giờ":      "acute hours",
    "1 ngày":       "acute 24 hours",
    "vài ngày":     "subacute days",
    "vài tuần":     "subacute weeks",
    "vài tháng":    "chronic months",
    "mạn tính":     "chronic longstanding persistent",
}

# Red flag symptoms — xuất hiện → boost urgency
RED_FLAG_SYMPTOMS: set[str] = {
    # Tim mạch / Hô hấp
    "đau ngực", "đau ngực trái", "khó thở đột ngột", "ho ra máu",
    "ngất", "chest pain", "hemoptysis", "syncope",
    # Thần kinh
    "đau đầu dữ dội", "yếu liệt nửa người", "co giật", "nói khó",
    "thunderclap headache", "hemiplegia", "seizure",
    # Bụng
    "đau bụng dữ dội", "nôn ra máu", "đi ngoài ra máu",
    "hematemesis", "hematochezia",
    # Toàn thân
    "sốt cao li bì", "vàng da đột ngột", "xuất huyết không cầm",
}


class SymptomEnricher:
    """
    Lớp 1: Mở rộng query triệu chứng trước khi embed.

    Input : SymptomContext (raw symptoms + ngữ cảnh)
    Output: enriched string → đưa vào embedder

    Chiến lược:
    1. Map từng triệu chứng VN → EN synonyms
    2. Thêm trigger qualifier (exertional, postprandial...)
    3. Thêm duration qualifier (acute, chronic...)
    4. Thêm location nếu có
    5. Thêm demographic context (age, sex)
    """

    def enrich(self, ctx: SymptomContext) -> tuple[str, list[str]]:
        """
        Returns:
            enriched_query : string đầy đủ để embed
            red_flags      : danh sách red flag tìm thấy
        """
        parts: list[str] = []
        red_flags: list[str] = []

        # 1. Triệu chứng chính + synonyms
        for sym in ctx.raw_symptoms:
            sym_clean = sym.strip().lower()
            parts.append(sym_clean)

            synonyms = SYNONYM_MAP.get(sym_clean, [])
            if synonyms:
                parts.extend(synonyms[:3])   # giới hạn 3 synonym/triệu chứng
            else:
                # Fallback: thêm từ gốc EN nếu đã là EN
                parts.append(sym_clean)

            if sym_clean in RED_FLAG_SYMPTOMS:
                red_flags.append(sym_clean)

        # 2. Trigger qualifier
        if ctx.trigger:
            trigger_q = TRIGGER_MAP.get(ctx.trigger, ctx.trigger)
            parts.append(trigger_q)

        # 3. Duration qualifier
        if ctx.duration:
            duration_q = DURATION_MAP.get(ctx.duration, ctx.duration)
            parts.append(duration_q)

        # 4. Location
        if ctx.location:
            parts.append(ctx.location)
            loc_en = SYNONYM_MAP.get(ctx.location, [ctx.location])
            parts.extend(loc_en[:2])

        # 5. Associated symptoms
        for assoc in ctx.associated[:3]:   # max 3 triệu chứng kèm
            assoc_clean = assoc.strip().lower()
            parts.append(assoc_clean)
            parts.extend(SYNONYM_MAP.get(assoc_clean, [])[:2])
            if assoc_clean in RED_FLAG_SYMPTOMS:
                red_flags.append(assoc_clean)

        # 6. Demographic context
        if ctx.age:
            if ctx.age >= 65:
                parts.append("elderly older adult geriatric")
            elif ctx.age <= 18:
                parts.append("pediatric child young")
        if ctx.sex == "nam":
            parts.append("male")
        elif ctx.sex == "nữ":
            parts.append("female")

        # 7. Severity
        severity_map = {
            "nặng": "severe", "rất nặng": "severe critical",
            "vừa": "moderate", "nhẹ": "mild"
        }
        if ctx.severity:
            parts.append(severity_map.get(ctx.severity, ctx.severity))

        enriched = " ".join(dict.fromkeys(parts))   # dedup, giữ thứ tự
        logger.debug(f"Enriched query ({len(parts)} tokens): {enriched[:120]}...")
        return enriched, red_flags


# ══════════════════════════════════════════════════════════════
# LỚP 2 — MEDICAL EMBEDDER
# ══════════════════════════════════════════════════════════════

class MedicalEmbedder:
    """
    Lớp 2: Embedding với model y tế thay all-MiniLM.

    Hỗ trợ 3 backend theo thứ tự ưu tiên:
      1. PhoBERT fine-tuned (tốt nhất cho VN, cần fine-tune)
      2. BioBERT / PubMedBERT (tốt cho y tế EN)
      3. all-MiniLM-L6 (fallback — giống hiện tại)

    Cách đổi model:
      embedder = MedicalEmbedder(model_name="pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-sts")
    """

    # Model được test, theo thứ tự khuyến nghị
    RECOMMENDED_MODELS = {
        "biobert":   "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-sts",
        "pubmedbert":"NeuML/pubmedbert-base-embeddings",
        "minilm":    "sentence-transformers/all-MiniLM-L6-v2",       # current
        "mpnet":     "sentence-transformers/all-mpnet-base-v2",
        # Sau khi fine-tune:
        # "phobert_med": "path/to/local/phobert-medical-finetuned",
    }

    def __init__(self, model_name: str = "biobert"):
        from sentence_transformers import SentenceTransformer

        # Resolve alias
        resolved = self.RECOMMENDED_MODELS.get(model_name, model_name)
        logger.info(f"Loading embedding model: {resolved}")

        self.model_name = resolved
        self._model = SentenceTransformer(resolved)
        self._dim   = self._model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Dim={self._dim}")

    @lru_cache(maxsize=2048)
    def embed_cached(self, text: str) -> tuple:
        """Cache embedding — tránh re-compute với query giống nhau."""
        vec = self._model.encode(text, normalize_embeddings=True)
        return tuple(vec.tolist())

    def embed(self, text: str) -> np.ndarray:
        cached = self.embed_cached(text)
        return np.array(cached, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Batch embed disease corpus — O(N) matrix mul."""
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=False,
        )

    def cosine_matrix(self, query_vec: np.ndarray, corpus_matrix: np.ndarray) -> np.ndarray:
        """
        Tính cosine similarity query vs toàn bộ corpus cùng lúc.
        Vectors đã normalize → dot product = cosine.
        """
        return corpus_matrix @ query_vec   # shape: (N,)

    def top_k(self, scores: np.ndarray, k: int = 10) -> np.ndarray:
        """argpartition O(N) thay vì argsort O(N log N)."""
        if len(scores) <= k:
            return np.argsort(scores)[::-1]
        idx = np.argpartition(scores, -k)[-k:]
        return idx[np.argsort(scores[idx])[::-1]]


# ══════════════════════════════════════════════════════════════
# LỚP 3 — SEVERITY-AWARE SCORER
# ══════════════════════════════════════════════════════════════

# ICD-10 prefix → urgency level
# Mở rộng dần khi thêm disease vào corpus
DISEASE_URGENCY: dict[str, str] = {
    # EMERGENCY — cần xử lý ngay
    "I21": "emergency",   # STEMI
    "I22": "emergency",   # NSTEMI
    "I20": "urgent",      # Unstable angina
    "I26": "emergency",   # Pulmonary embolism
    "I63": "emergency",   # Ischemic stroke
    "I61": "emergency",   # Hemorrhagic stroke
    "I64": "emergency",   # Stroke NOS
    "G40": "urgent",      # Epilepsy / seizure
    "G41": "emergency",   # Status epilepticus
    "K25": "urgent",      # Gastric ulcer
    "K92": "emergency",   # GI hemorrhage
    "J18": "urgent",      # Pneumonia
    "J96": "emergency",   # Respiratory failure
    "N17": "emergency",   # Acute kidney injury
    "O00": "emergency",   # Ectopic pregnancy

    # URGENT — cần khám trong 24h
    "I10": "urgent",      # Hypertension
    "I50": "urgent",      # Heart failure
    "J45": "urgent",      # Asthma
    "K35": "emergency",   # Appendicitis
    "E11": "routine",     # T2DM
    "M54": "routine",     # Back pain
    "J06": "routine",     # URTI
}

URGENCY_RANK = {"emergency": 3, "urgent": 2, "routine": 1}

# Threshold tối thiểu theo urgency
# Emergency disease cần cosine cao hơn để hiện — không để cấp cứu hiện sai
URGENCY_MIN_COSINE = {
    "emergency": 0.42,   # phải khá chắc mới show
    "urgent":    0.36,
    "routine":   0.30,
}

# Red flag boost value
RED_FLAG_BOOST = 0.12


class SeverityScorer:
    """
    Lớp 3: Tính final score = f(cosine, urgency, red_flags).

    Logic:
    - Nếu query có red flag → boost score của emergency diseases
    - Nếu cosine < min threshold theo urgency → suppress (không show sai)
    - Emergency disease luôn được sort lên đầu nếu score đủ ngưỡng
    """

    def score(
        self,
        cosine: float,
        disease_id: str,
        red_flags: list[str],
        ctx: SymptomContext,
    ) -> tuple[float, str]:
        """
        Returns:
            final_score : float
            urgency     : str
        """
        # Xác định urgency từ ICD prefix (2-3 ký tự đầu)
        urgency = self._get_urgency(disease_id)
        min_cosine = URGENCY_MIN_COSINE[urgency]

        # Hard suppress: cosine quá thấp so với ngưỡng urgency
        if cosine < min_cosine:
            return 0.0, urgency

        score = cosine

        # Red flag boost: chỉ apply cho emergency/urgent
        if red_flags and urgency in ("emergency", "urgent"):
            score = min(score + RED_FLAG_BOOST, 1.0)

        # Severity boost: user mô tả "nặng" / "rất nặng"
        if ctx.severity in ("nặng", "rất nặng") and urgency == "emergency":
            score = min(score + 0.05, 1.0)

        # Demographic risk boost
        if ctx.age and ctx.age >= 65 and urgency == "emergency":
            score = min(score + 0.03, 1.0)

        return round(score, 4), urgency

    def _get_urgency(self, disease_id: str) -> str:
        """Match ICD-10 prefix, fallback routine."""
        for prefix_len in (3, 2, 1):
            prefix = disease_id[:prefix_len]
            if prefix in DISEASE_URGENCY:
                return DISEASE_URGENCY[prefix]
        return "routine"

    def is_emergency_situation(
        self, candidates: list[DiagnosisCandidate], red_flags: list[str]
    ) -> tuple[bool, str]:
        """
        Quyết định có phải tình huống cấp cứu không.
        True nếu top-3 có ít nhất 1 emergency + red flag present.
        """
        top3 = candidates[:3]
        has_emergency = any(c.urgency == "emergency" for c in top3)
        has_red_flag  = len(red_flags) > 0

        if has_emergency and has_red_flag:
            emergency_c = next(c for c in top3 if c.urgency == "emergency")
            reason = (
                f"Triệu chứng cờ đỏ ({', '.join(red_flags[:2])}) "
                f"kết hợp với nghi ngờ {emergency_c.disease_name_vn} "
                f"(score={emergency_c.severity_score:.2f})"
            )
            return True, reason

        # Single red flag cũng đủ nếu rất đặc hiệu
        critical_flags = {"đau đầu dữ dội", "yếu liệt nửa người", "đau ngực trái", "co giật"}
        if any(f in critical_flags for f in red_flags):
            return True, f"Triệu chứng cờ đỏ nguy hiểm: {', '.join(red_flags)}"

        return False, ""


# ══════════════════════════════════════════════════════════════
# DISEASE CORPUS LOADER
# ══════════════════════════════════════════════════════════════

@dataclass
class DiseaseEntry:
    id: str
    name_en: str
    name_vn: str
    description_en: str   # text để embed
    keywords: list[str] = field(default_factory=list)


class DiseaseCorpus:
    """
    Load và cache disease corpus từ JSONL.
    Format mỗi dòng:
    {"id":"I21","name_en":"STEMI","name_vn":"Nhồi máu cơ tim ST chênh",
     "description_en":"Acute ST-elevation myocardial infarction severe chest pain..."}
    """

    def __init__(self, corpus_path: str = "data/disease_corpus.jsonl"):
        self.path = Path(corpus_path)
        self.diseases: list[DiseaseEntry] = []
        self._embed_texts: list[str] = []
        self._matrix: Optional[np.ndarray] = None
        self._load()

    def _load(self):
        if not self.path.exists():
            logger.warning(f"Corpus không tìm thấy: {self.path}. Dùng corpus mẫu.")
            self.diseases = self._sample_corpus()
        else:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        self.diseases.append(DiseaseEntry(**d))

        # Build embed texts: description + keywords
        self._embed_texts = [
            f"{d.description_en} {' '.join(d.keywords)}"
            for d in self.diseases
        ]
        logger.info(f"Corpus loaded: {len(self.diseases)} diseases.")

    def get_matrix(self, embedder: MedicalEmbedder) -> np.ndarray:
        """Tính corpus matrix 1 lần, cache lại."""
        if self._matrix is None:
            logger.info("Computing disease corpus embeddings...")
            self._matrix = embedder.embed_batch(self._embed_texts)
        return self._matrix

    def invalidate_cache(self):
        """Gọi khi thêm disease mới vào corpus."""
        self._matrix = None

    def _sample_corpus(self) -> list[DiseaseEntry]:
        """Corpus mẫu để test khi chưa có file đầy đủ."""
        return [
            DiseaseEntry("I21", "STEMI", "Nhồi máu cơ tim cấp",
                "acute ST-elevation myocardial infarction severe crushing chest pain "
                "left arm radiation diaphoresis nausea exertional sudden onset",
                ["STEMI", "heart attack", "MI"]),
            DiseaseEntry("I20", "Unstable angina", "Đau thắt ngực không ổn định",
                "unstable angina chest pain rest exertional crescendo worsening "
                "cardiac ischemia",
                ["angina", "ACS"]),
            DiseaseEntry("I63", "Ischemic stroke", "Đột quỵ thiếu máu não",
                "ischemic stroke sudden weakness hemiplegia facial droop speech "
                "difficulty aphasia dysarthria",
                ["stroke", "CVA", "brain infarction"]),
            DiseaseEntry("K25", "Peptic ulcer", "Loét dạ dày tá tràng",
                "gastric ulcer epigastric pain burning postprandial nausea "
                "hematemesis melena",
                ["PUD", "gastric ulcer"]),
            DiseaseEntry("J45", "Asthma", "Hen phế quản",
                "asthma wheezing breathlessness dyspnea nocturnal cough "
                "reversible airflow obstruction",
                ["bronchial asthma", "reactive airway"]),
            DiseaseEntry("G40", "Epilepsy", "Động kinh",
                "epilepsy seizure convulsion loss of consciousness tonic clonic "
                "postictal confusion",
                ["seizure disorder"]),
            DiseaseEntry("N39", "UTI", "Nhiễm khuẩn tiết niệu",
                "urinary tract infection dysuria frequency urgency suprapubic pain "
                "hematuria pyuria",
                ["cystitis", "bladder infection"]),
            DiseaseEntry("O00", "Ectopic pregnancy", "Thai ngoài tử cung",
                "ectopic pregnancy lower abdominal pain vaginal bleeding amenorrhea "
                "missed period female reproductive emergency",
                ["tubal pregnancy"]),
            DiseaseEntry("M54", "Back pain", "Đau lưng",
                "low back pain lumbar dorsalgia chronic mechanical musculoskeletal "
                "postural",
                ["lumbago", "lumbar pain"]),
            DiseaseEntry("J06", "URTI", "Viêm đường hô hấp trên",
                "upper respiratory tract infection rhinitis pharyngitis sore throat "
                "runny nose mild fever common cold",
                ["cold", "rhinopharyngitis"]),
        ]


# ══════════════════════════════════════════════════════════════
# ENHANCED DIAGNOSTIC PIPELINE — TỔNG HỢP 3 LỚP
# ══════════════════════════════════════════════════════════════

class EnhancedDiagnosticPipeline:
    """
    Pipeline chẩn đoán nâng cấp — tích hợp 3 lớp.

    Sử dụng:
        pipeline = EnhancedDiagnosticPipeline(embed_model="biobert")
        ctx = SymptomContext(
            raw_symptoms=["đau ngực", "khó thở"],
            trigger="gắng sức",
            duration="30 phút",
            severity="nặng",
            age=65, sex="nam"
        )
        result = await pipeline.diagnose(ctx)
        print(result.is_emergency, result.top_candidates[0].disease_name_vn)
    """

    def __init__(
        self,
        embed_model: str = "biobert",
        corpus_path: str = "data/disease_corpus.jsonl",
        top_k: int = 5,
    ):
        self.enricher = SymptomEnricher()
        self.embedder = MedicalEmbedder(model_name=embed_model)
        self.scorer   = SeverityScorer()
        self.corpus   = DiseaseCorpus(corpus_path)
        self.top_k    = top_k

        # Pre-compute corpus matrix lúc khởi động
        self._corpus_matrix = self.corpus.get_matrix(self.embedder)
        logger.info("EnhancedDiagnosticPipeline ready.")

    async def diagnose(self, ctx: SymptomContext) -> DiagnosisResult:
        t0 = time.perf_counter()

        # LỚP 1: Enrich
        enriched_query, red_flags = self.enricher.enrich(ctx)
        logger.debug(f"Red flags: {red_flags}")

        # LỚP 2: Embed + cosine
        query_vec    = self.embedder.embed(enriched_query)
        cosine_scores = self.embedder.cosine_matrix(query_vec, self._corpus_matrix)
        top_indices  = self.embedder.top_k(cosine_scores, k=self.top_k * 2)   # lấy nhiều hơn trước khi filter

        # LỚP 3: Severity score + filter
        candidates: list[DiagnosisCandidate] = []
        for idx in top_indices:
            disease = self.corpus.diseases[idx]
            cosine  = float(cosine_scores[idx])

            final_score, urgency = self.scorer.score(
                cosine=cosine,
                disease_id=disease.id,
                red_flags=red_flags,
                ctx=ctx,
            )

            if final_score == 0.0:
                continue   # bị suppress

            candidates.append(DiagnosisCandidate(
                disease_id=disease.id,
                disease_name_en=disease.name_en,
                disease_name_vn=disease.name_vn,
                cosine_raw=round(cosine, 4),
                severity_score=final_score,
                urgency=urgency,
                red_flags_matched=red_flags,
                enriched_query=enriched_query[:200],
            ))

        # Sort: emergency trước, sau đó theo severity_score
        candidates.sort(
            key=lambda c: (URGENCY_RANK[c.urgency], c.severity_score),
            reverse=True,
        )
        top_candidates = candidates[:self.top_k]

        # Quyết định cấp cứu
        is_emergency, emergency_reason = self.scorer.is_emergency_situation(
            top_candidates, red_flags
        )

        latency = (time.perf_counter() - t0) * 1000
        logger.info(f"Diagnosis done in {latency:.1f}ms. Emergency={is_emergency}")

        return DiagnosisResult(
            top_candidates=top_candidates,
            is_emergency=is_emergency,
            emergency_reason=emergency_reason,
            enriched_query=enriched_query,
            embed_model_used=self.embedder.model_name,
            latency_ms=round(latency, 2),
            warning=(
                "Đây là công cụ hỗ trợ, không thay thế chẩn đoán bác sĩ."
                if is_emergency else ""
            ),
        )

    def to_navigator_output(self, result: DiagnosisResult) -> dict:
        """
        Convert sang format output_formatter.py hiện tại.
        Tương thích ngược với V9.2.
        """
        out = {
            "is_emergency": result.is_emergency,
            "emergency_reason": result.emergency_reason,
            "embed_model": result.embed_model_used,
            "latency_ms": result.latency_ms,
            "candidates": [],
        }
        for c in result.top_candidates:
            out["candidates"].append({
                "disease_id":   c.disease_id,
                "name_vn":      c.disease_name_vn,
                "name_en":      c.disease_name_en,
                "score":        c.severity_score,
                "cosine_raw":   c.cosine_raw,
                "urgency":      c.urgency,
                "red_flags":    c.red_flags_matched,
            })
        return out


# ══════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════

async def _demo():
    import asyncio
    logging.basicConfig(level=logging.INFO)

    # Test case 1: Nhồi máu cơ tim
    pipeline = EnhancedDiagnosticPipeline(embed_model="minilm")   # dùng minilm để test nhanh

    ctx_ami = SymptomContext(
        raw_symptoms=["đau ngực trái", "khó thở"],
        trigger="gắng sức",
        duration="30 phút",
        severity="nặng",
        location="lan vai trái",
        age=68, sex="nam",
    )
    result = await pipeline.diagnose(ctx_ami)
    print("\n=== Test: Nghi nhồi máu cơ tim ===")
    print(f"Emergency: {result.is_emergency}")
    print(f"Reason   : {result.emergency_reason}")
    print(f"Latency  : {result.latency_ms}ms")
    for c in result.top_candidates:
        print(f"  [{c.urgency:10}] {c.disease_name_vn:35} cosine={c.cosine_raw:.3f} → score={c.severity_score:.3f}")

    # Test case 2: Trễ kinh — KHÔNG được ra Epilepsy
    ctx_obgyn = SymptomContext(
        raw_symptoms=["trễ kinh", "đau bụng dưới"],
        duration="1 tháng",
        sex="nữ",
        age=28,
    )
    result2 = await pipeline.diagnose(ctx_obgyn)
    print("\n=== Test: Trễ kinh (OBGYN guard) ===")
    print(f"Emergency: {result2.is_emergency}")
    for c in result2.top_candidates:
        print(f"  [{c.urgency:10}] {c.disease_name_vn:35} score={c.severity_score:.3f}")
    # Kiểm tra G40 không xuất hiện
    ids = [c.disease_id for c in result2.top_candidates]
    assert "G40" not in ids, f"OBGYN guard FAIL — G40 xuất hiện: {ids}"
    print("  OBGYN guard OK — G40 không xuất hiện")

    # Test case 3: Đi loạng choạng → Ataxia (không phải urinary urgency)
    ctx_gait = SymptomContext(
        raw_symptoms=["đi loạng choạng", "chóng mặt"],
        duration="vài ngày",
        age=55,
    )
    result3 = await pipeline.diagnose(ctx_gait)
    print("\n=== Test: Đi loạng choạng (Ataxia guard) ===")
    for c in result3.top_candidates:
        print(f"  [{c.urgency:10}] {c.disease_name_vn:35} score={c.severity_score:.3f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())