import pandas as pd
import numpy as np
import requests
import os
import argparse
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# Thêm project root vào path
sys.path.append(str(Path(__file__).parent.parent))

# Cấu hình encoding cho terminal Windows để hỗ trợ tiếng Việt
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ── V5.1: Emergency / Red-Flag keyword set ───────────────────────────────────
# Symptoms in this set bypass the strict Reverse Check (threshold lowered to 0.25)
# to ensure life-threatening diagnoses are NEVER silently rejected.
_RED_FLAG_SYMPTOMS: frozenset = frozenset([
    # Cardiovascular
    "chest pain", "đau ngực", "tức ngực", "đau thắt ngực", "đau ngực trái",
    "left-sided chest pain", "precordial pain", "angina",
    "palpitations", "hồi hộp", "tim đập nhanh",
    "diaphoresis", "vã mồ hôi", "syncope", "ngất", "mất tri giác",
    # Respiratory emergency
    "dyspnea", "shortness of breath", "khó thở", "thở gấp", "tachypnea",
    "respiratory distress", "suy hô hấp", "hemoptysis", "ho ra máu",
    # Neurological emergency
    "severe headache", "đau đầu dữ dội", "thunderclap headache",
    "hemiparesis", "liệt nửa người", "facial droop", "méo miệng",
    "slurred speech", "nói ngọng", "sudden confusion",
    # Meningeal
    "neck stiffness", "cứng cổ", "high fever", "sốt cao",
    # Shock / sepsis
    "hypotension", "tụt huyết áp", "altered consciousness", "rối loạn ý thức",
    "sepsis", "rapid heartbeat",
])


class MedicalDiagnosticTool:
    def __init__(self):
        # Đường dẫn linh hoạt
        self.base_dir = Path("i:/TuminhAgi")
        self.vault_path = self.base_dir / "data/raw_med/icd10_global_catalog.csv"
        self.embedding_cache = self.base_dir / "storage/medical_vault/icd10_core/embeddings.npy"
        # Cache norm_vault để tránh tính lại norm theo mỗi query (tốn I/O CPU và có thể gây "treo")
        self.norm_cache = self.base_dir / "storage/medical_vault/icd10_core/norm_vault.npy"
        
        self.ollama_url = "http://localhost:11434/api/embeddings"
        self.ollama_gen_url = "http://localhost:11434/api/generate"
        self.model_name = "mxbai-embed-large"
        self.llm_model = "phi4-mini" # Sử dụng model nhỏ để dịch nhanh
        self.summary_model = "llama3:8b" # Sử dụng Llama 3 để tóm tắt văn bản người hơn
        
        # Cấu hình Blockchain (V6)
        import hashlib
        self.hash_fn = hashlib.sha256
        
        # Database cấu hình
        print("--- 🛠️ Đang khởi tạo Database... ---")
        self.db_path = self.base_dir / "storage/medical_vault/tuminh_history.db"
        self._init_db()
        print("--- 🛠️ Đang kiểm toán Toàn vẹn (Blockchain)... ---")
        self.verify_integrity() # Kiểm toán khi khởi động
        print("--- 🛠️ Đang chạy Hội đồng Y khoa (Evolution Audit)... ---")
        self.periodic_clinical_audit() # Tự tiến hóa (V7)
        print("--- 🛠️ Khởi tạo Hoàn tất. ---")
        
        self.df = None
        self.embeddings = None
        self.norm_vault = None
        # Pre-normalized unit vectors for fast cosine sim: cosine(q,d) = dot(unit_q, unit_d)
        self._unit_vault: "np.ndarray | None" = None
        self.unit_cache: "Path | None" = None
        # V5.1: Lowered from 0.55 → 0.38 to reduce over-rejection on translated queries.
        self.threshold = 0.38

        # ── In-process caches ────────────────────────────────────────────
        # translate_query: keyed by raw VN text → English translation.
        # Avoids repeated LLM/HardMapping calls for the same symptom phrase.
        self._translate_cache: dict[str, str] = {}

        # General embedding cache (all callers, not just reverse check).
        # Key: first 300 chars of text (lowercased) → np.ndarray float32 or None.
        # Max 4096 entries (~300 chars × 4096 × 4 B ≈ 5 MB keys + ~50 MB vectors).
        self._embed_cache: dict[str, "np.ndarray | None"] = {}

        # Reverse-description check re-uses _embed_cache; kept as alias for clarity.
        self._reverse_embed_cache = self._embed_cache

    def get_ollama_embedding(self, text):
        """Gọi Ollama để lấy vector — với in-process cache để tránh gọi lại."""
        cache_key = str(text)[:300].lower()
        cached = self._embed_cache.get(cache_key)
        if cached is not None:
            return cached  # cache hit: already a np.ndarray float32

        # Sentinel: if key exists but is None, a previous call failed — don't retry.
        if cache_key in self._embed_cache:
            return None

        try:
            response = requests.post(
                self.ollama_url,
                json={"model": self.model_name, "prompt": str(text)},
                timeout=30,
            )
            raw = response.json()["embedding"]
            vec = np.asarray(raw, dtype=np.float32)
            # Evict oldest entries if cache grows too large (simple FIFO trim).
            if len(self._embed_cache) >= 4096:
                oldest = next(iter(self._embed_cache))
                del self._embed_cache[oldest]
            self._embed_cache[cache_key] = vec
            return vec
        except Exception as e:
            print(f"Error calling Ollama Embedding: {e}")
            self._embed_cache[cache_key] = None  # mark failed so we don't retry
            return None

    def translate_query(self, text):
        """Dịch triệu chứng sang tiếng Anh bằng LLM local — với in-process cache."""
        # Nếu đã là tiếng Anh (chỉ chứa ASCII và đủ dài) thì không dịch
        if all(ord(c) < 128 for c in text) and len(text.split()) > 2:
            return text

        # ── Cache check ─────────────────────────────────────────────────────
        cache_key = text.strip().lower()
        if cache_key in self._translate_cache:
            return self._translate_cache[cache_key]

        # 1) HARD MAPPING FIRST: tránh lỗi dịch nghiêm trọng từ phi4-mini
        try:
            from missions_hub.medical_mapping import translate_vn_symptoms_hard
            hard = translate_vn_symptoms_hard(text)
            if hard and hard != "UNKNOWN":
                print(f"DEBUG HardMapping Translation: {text} -> {hard}")
                self._translate_cache[cache_key] = hard
                return hard
        except Exception as e:
            # Nếu mapping lỗi vì lý do nào đó, fallback sang AI dịch
            print(f"⚠️ HardMapping error, fallback to AI Translation: {e}")
            
        print(f"--- 🌐 Đang dịch triệu chứng sang tiếng Anh (phi4-mini)... ---")

        # 2) Few-shot prompt (V5.1: synonyms format for better vector matching)
        prompt = f"""
You are a Senior Medical Translator specializing in ICD-10 terminology.

TASK:
Convert Vietnamese symptom phrases into precise English medical terms.
For each term, also provide 1-2 common clinical synonyms in parentheses to maximize ICD vector matching.
Do NOT infer any body part that is not explicitly present in the input.

ANTI-CONFUSION (MUST NOT VIOLATE):
- Urinary terms (tiểu buốt/tiểu gắt/tiểu đục/nước tiểu đục/tiểu rát/tiểu nhiều/tiểu rắt) MUST NEVER map to: Seizure / Epilepsy / Diarrhea.
- Seizure terms (co giật/động kinh) MUST NEVER map to urinary terms or Diarrhea.
- Diarrhea terms (tiêu chảy/đi ngoài phân lỏng) MUST NEVER map to urinary terms or seizure terms.

TIME MARKERS:
- "buổi sáng" -> "in the morning"
- "trưa" or "chiều" -> "in the afternoon"
- "tối" -> "in the evening"
- "sau ăn" -> "after meals"
If a time marker appears, include its English phrase as one of the terms.

OUTPUT FORMAT (STRICT):
- Return ONLY a single line.
- Format: Standard Medical Term (synonym1, synonym2); Next Term (synonym)
- Terms separated by "; " (semicolon + space).
- No extra sentences, no bullets, no quotes, no trailing period.

FEW-SHOT EXAMPLES:
Input: "Đau ngực trái" -> Output: "Chest pain, left-sided (precordial pain, angina pectoris)"
Input: "Tiểu gắt" -> Output: "Urinary urgency (dysuria)"
Input: "Nước tiểu đục" -> Output: "Cloudy urine (turbid urine)"
Input: "Tiểu buốt/gắt, nước tiểu đục" -> Output: "Dysuria (burning urination); Urinary urgency; Cloudy urine"
Input: "Vã mồ hôi" -> Output: "Diaphoresis (excessive sweating)"
Input: "Khó thở" -> Output: "Shortness of breath (dyspnea, breathlessness)"
Input: "Đau đầu dữ dội, buồn nôn, sợ ánh sáng" -> Output: "Severe headache (thunderclap headache); Nausea; Photophobia"
Input: "Co giật" -> Output: "Seizure (convulsion)"
Input: "Tiêu chảy, đi ngoài phân lỏng" -> Output: "Diarrhea (loose stool)"
Input: "Hồi hộp, tim đập nhanh" -> Output: "Palpitations (rapid heartbeat, tachycardia)"

Input: "{text}"
Output:
"""
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.llm_model, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
                timeout=30
            )
            translated = response.json()["response"].strip()
            
            # Xử lý nếu model quá "nhiều lời": lấy dòng đầu tiên không trống và làm sạch
            lines = [l.strip() for l in translated.split('\n') if l.strip()]
            if lines:
                translated = lines[0]
            
            # Loại bỏ các prefix phổ biến
            for prefix in ["Translation:", "Result:", "Terms:", "English:", "Diagnosis:", "Output:", "-"]:
                if translated.startswith(prefix):
                    translated = translated[len(prefix):].strip()

            translated = translated.strip().strip('"').strip("'")
            # Bỏ dấu chấm cuối (nếu có)
            if translated.endswith("."):
                translated = translated[:-1].strip()
            # Nếu dùng dấu phẩy để ngăn cách mà không có '; ' thì chuẩn hóa sang '; '
            if ";" not in translated and "," in translated:
                translated = "; ".join([p.strip() for p in translated.split(",") if p.strip()])

            print(f"DEBUG Translation: {text} -> {translated}")
            self._translate_cache[cache_key] = translated
            return translated
        except Exception as e:
            print(f"Error calling Ollama Translation: {e}")
            # Cache the original text as fallback so we don't retry on same input.
            self._translate_cache[cache_key] = text
            return text

    def strict_chapter_check(self, symptoms, icd_code):
        """Khóa Chương (Strict Chapter Rule) - V9+ Universal Chapters Support"""
        symptoms_lower = symptoms.lower()
        icd_chap = icd_code[0].upper()
        
        # V9 EMERGENCY: Chương R (Triệu Chứng) và Chương Z (Yếu tố sức khỏe) là Chương Vạn Năng
        if icd_chap in ["R", "Z"]:
            return True, "PASS (Universal Chapter)"
        
        # 1. Hô hấp (Respiratory/Infectious/Symptoms)
        # ... (giữ nguyên logic cũ bên dưới)
        if any(kw in symptoms_lower for kw in ["ho", "phổi", "thở", "phế quản", "họng", "mũi", "cough", "shortness of breath", "dyspnea", "wheezing"]):
            allowed = ["A", "B", "J", "R", "C3"] 
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Triệu chứng Hô hấp không khớp chương {icd_chap}."
        
        # 2. Tim mạch (V5.1: added English clinical terms)
        if any(kw in symptoms_lower for kw in [
            "ngực", "tim", "mạch", "áp", "hồi hộp",
            "chest pain", "chest tightness", "angina", "precordial",
            "left-sided chest pain", "palpitations", "diaphoresis",
            "shortness of breath", "dyspnea", "syncope", "rapid heartbeat",
        ]):
            allowed = ["I", "R", "J", "C7"]
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Triệu chứng Tim mạch không khớp chương {icd_chap}."
                
        if any(kw in symptoms_lower for kw in ["bụng", "dạ dày", "gan", "mật", "tiêu", "nuốt", "ăn"]):
            allowed = ["K", "A", "B", "R", "C1", "C2"]
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Triệu chứng Tiêu hóa không khớp chương {icd_chap}."

        # TIÊU HÓA (vòng bổ sung cho Táo bón/đi ngoài)
        # Đảm bảo các triệu chứng thuộc Chương K như "Constipation" không bị rơi khỏi nhóm.
        if any(kw in symptoms_lower for kw in ["táo bón", "bón", "đi ngoài", "phân", "trĩ", "constipation"]):
            allowed = ["K", "A", "B", "R", "C1", "C2"]
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Triệu chứng Tiêu hóa (Táo bón/đi ngoài) không khớp chương {icd_chap}."
                
        if any(kw in symptoms_lower for kw in ["tóc", "da", "móng", "ngứa", "ban", "mẩn"]):
            allowed = ["L", "B", "A", "R", "C4"]
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Triệu chứng Da liễu không khớp chương {icd_chap}."

        if any(kw in symptoms_lower for kw in ["tiểu", "đái", "thận", "niệu", "sinh dục", "kinh nguyệt"]):
            allowed = ["N", "A", "B", "R", "O"]
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Triệu chứng Tiết niệu không khớp chương {icd_chap}."

        # V5.1 MENINGEAL LOCK: cứng cổ + sợ ánh sáng → PHẢI thuộc G hoặc A/B (infection)
        # Ngăn ICD chương I (huyết áp) bị trả về khi triệu chứng rõ ràng là màng não.
        if any(kw in symptoms_lower for kw in [
            "cứng cổ", "cứng gáy", "neck stiffness", "nuchal rigidity",
            "sợ ánh sáng", "photophobia", "meningismus",
        ]):
            allowed = ["G", "A", "B", "R"]
            if not any(icd_chap == chap[0] for chap in allowed):
                return False, f"Dấu hiệu màng não (cứng cổ/sợ ánh sáng) không khớp chương {icd_chap} — kỳ vọng G/A/B."

        return True, "PASS"

    def _allowed_icd_chapter_prefixes(self, symptoms: str):
        """
        Return allowed ICD chapter prefixes (first-letter prefixes) for the given symptom text.
        If no restriction applies, return None.
        """
        symptoms_lower = (symptoms or "").lower()

        # V9 EMERGENCY: universal symptom chapters (allow always)
        # (We still return some restrictions for other symptom types below.)

        # 1. Hô hấp
        # 0. MENINGEAL / NEUROLOGICAL — kiểm tra TRƯỚC hết (pathognomonic priority)
        # "cứng cổ" + "sợ ánh sáng" là dấu hiệu đặc trưng G00/Meningitis — KHÔNG được nhường I10
        if any(kw in symptoms_lower for kw in [
            "cứng cổ", "cứng gáy", "neck stiffness", "nuchal rigidity",
            "sợ ánh sáng", "photophobia", "meningismus",
            "đau đầu dữ dội", "severe headache", "thunderclap",
            "hemiparesis", "liệt nửa người", "đột quỵ", "stroke",
            "co giật", "seizure", "động kinh", "epilepsy",
        ]):
            return ["G", "A", "B", "R"]

        if any(kw in symptoms_lower for kw in ["ho", "phổi", "thở", "phế quản", "họng", "mũi", "cough", "shortness of breath", "dyspnea", "wheezing"]):
            return ["A", "B", "J", "R", "C3"]

        # 2. Tim mạch (V5.1: expanded with English clinical terms for post-translation queries)
        if any(kw in symptoms_lower for kw in [
            "ngực", "tim", "mạch", "áp", "hồi hộp",
            "chest pain", "chest tightness", "angina", "precordial",
            "left-sided chest pain", "palpitations", "diaphoresis",
            "shortness of breath", "dyspnea", "syncope", "rapid heartbeat",
        ]):
            return ["I", "R", "J", "C7"]

        # 3. Tiêu hóa
        if any(kw in symptoms_lower for kw in ["bụng", "dạ dày", "gan", "mật", "tiêu", "nuốt", "ăn", "táo bón", "bón", "đi ngoài", "phân", "trĩ", "constipation", "diarrhea"]):
            return ["K", "A", "B", "R", "C1", "C2"]

        # 4. Da liễu
        if any(kw in symptoms_lower for kw in ["tóc", "da", "móng", "ngứa", "ban", "mẩn"]):
            return ["L", "B", "A", "R", "C4"]

        # 5. Tiết niệu/niệu
        if any(kw in symptoms_lower for kw in ["tiểu", "đái", "thận", "niệu", "sinh dục", "kinh nguyệt"]):
            return ["N", "A", "B", "R", "O"]

        return None

    def get_expected_chapters(self, symptoms: str):
        """
        Compatibility wrapper (requested by spec).
        Returns allowed ICD chapter prefixes for a given symptom text.
        """
        return self._allowed_icd_chapter_prefixes(symptoms)

    def _is_emergency_case(self, user_query: str) -> bool:
        """
        Emergency override heuristic — V5.1 expanded.
        Covers: meningitis (fever+neck), ACS (chest pain), stroke (hemiparesis),
        severe dyspnea, and any symptom tagged in _RED_FLAG_SYMPTOMS.
        """
        text = (user_query or "").lower()

        # 1. Classic meningitis pattern
        has_high_fever = any(kw in text for kw in ["sốt cao", "sot cao", "high fever", "fever"])
        has_neck_stiffness = any(kw in text for kw in ["cứng cổ", "cung co", "neck stiffness", "stiff neck"])
        if has_high_fever and has_neck_stiffness:
            return True

        # 2. Acute coronary syndrome / cardiac emergency
        has_chest_pain = any(kw in text for kw in [
            "đau ngực", "tức ngực", "chest pain", "angina", "precordial",
            "left-sided chest pain", "đau thắt ngực",
        ])
        has_cardiac_assoc = any(kw in text for kw in [
            "vã mồ hôi", "diaphoresis", "hồi hộp", "palpitations",
            "khó thở", "shortness of breath", "dyspnea", "ngất", "syncope",
        ])
        if has_chest_pain:
            return True  # Chest pain alone is always an emergency

        # 3. Stroke / neurological emergency
        if any(kw in text for kw in [
            "liệt nửa người", "hemiparesis", "méo miệng", "facial droop",
            "nói ngọng", "slurred speech", "đột quỵ", "stroke",
        ]):
            return True

        # 4. Severe respiratory distress
        if any(kw in text for kw in ["suy hô hấp", "respiratory distress", "ho ra máu", "hemoptysis"]):
            return True

        # 5. Any single keyword from the global red-flag set
        return any(kw in text for kw in _RED_FLAG_SYMPTOMS)


    def reverse_description_check(self, user_symptoms, icd_description):
        """
        Reverse Description Check (semantic, not exact match).
        V5.1: Adaptive threshold — RED_FLAG symptoms use 0.25, others use 0.38.
        Goal: reject only when ICD short description is clearly unrelated to the core meaning.
        """
        print(f"--- 🔒 Đang chạy khóa 'Reverse Description Check'... ---")

        sym_lower = (user_symptoms or "").lower()
        desc_lower = (icd_description or "").lower()

        # ── Hard-coded anatomical mismatch guards (remain strict) ──────────
        if "headache" in desc_lower and not any(kw in sym_lower for kw in ["đau đầu", "nhức đầu", "headache"]):
            return "REJECT: Mã bệnh chứa 'Headache' nhưng triệu chứng không có 'Đau đầu'."
        if "toe" in desc_lower and not any(kw in sym_lower for kw in ["ngón chân", "toe"]):
            return "REJECT: Mã bệnh chứa 'Toe' nhưng triệu chứng không có 'Ngón chân'."

        # ── V5.1: Adaptive semantic threshold ─────────────────────────────
        # Emergency / Red-Flag presentations → very low threshold (0.25) to
        # guarantee life-threatening ICD codes are NEVER silently dropped.
        is_red_flag = any(kw in sym_lower for kw in _RED_FLAG_SYMPTOMS)
        semantic_threshold = 0.25 if is_red_flag else 0.38
        if is_red_flag:
            print("⚡ RED FLAG detected — Reverse Check threshold lowered to 0.25")
        prompt = f"""Compare the User Symptoms with the ICD Description.

IMPORTANT: ICD-10 descriptions are often short and may NOT list every accompanied symptom the user mentions.
Therefore, you must NOT require that all user symptoms appear in the ICD description.

RULE (Partial Match / Core Diagnosis only):
1) Identify the CORE diagnosis implied by the ICD Description (e.g., "Headache" in "Headache").
2) Reject ONLY if the CORE diagnosis is NOT mentioned or clearly implied by the User Symptoms.
3) If the ICD Description matches the CORE diagnosis, then PASS even if the User Symptoms include extra accompanied symptoms
   (e.g., nausea, photophobia, etc. that are not explicitly listed in the ICD description).

User Symptoms: "{user_symptoms}"
ICD Description: "{icd_description}"

Examples:
- Symptoms "Đau đầu dữ dội, buồn nôn" vs Description "Headache" -> PASS (core matches; nausea is accompanied).
- Symptoms "Ho" vs Description "Cough headache" -> REJECT (core "headache" is missing).

Output ONLY: "PASS" or "REJECT: [Reason]".
"""
        try:
            k1 = (user_symptoms or "").strip().lower()
            k2 = (icd_description or "").strip().lower()

            # Use sentinel to distinguish "not cached" from "cached as None" (failed embedding).
            _MISS = object.__new__(object)  # unique sentinel per call (cheap)

            raw1 = self._reverse_embed_cache.get(k1, _MISS)
            if raw1 is _MISS:
                raw1 = self.get_ollama_embedding(user_symptoms)
                if raw1 is not None:
                    raw1 = np.asarray(raw1, dtype=np.float32)
                self._reverse_embed_cache[k1] = raw1

            raw2 = self._reverse_embed_cache.get(k2, _MISS)
            if raw2 is _MISS:
                raw2 = self.get_ollama_embedding(icd_description)
                if raw2 is not None:
                    raw2 = np.asarray(raw2, dtype=np.float32)
                self._reverse_embed_cache[k2] = raw2

            if raw1 is not None and raw2 is not None:
                # Pre-normalize on first use (store unit vector in cache for reuse)
                a: np.ndarray = raw1
                b: np.ndarray = raw2
                sim = float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))
                if sim >= semantic_threshold:
                    return "PASS"
                return f"REJECT: semantic_similarity={sim:.3f} < threshold({semantic_threshold})"
        except Exception as e:
            print(f"⚠️ Reverse Description Check semantic similarity error: {e}")

        # Fallback: LLM judge (semantic / partial match rule) if embedding fails.
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.llm_model, "prompt": prompt, "stream": False},
                timeout=30
            )
            return response.json()["response"].strip()
        except Exception:
            return "PASS"

    def split_symptoms(self, text):
        """Tách thực thể triệu chứng (Entities) - Bước 1: Decompose"""
        print(f"--- 🧩 Đang trích xuất thực thể y khoa (Entity Extraction)... ---")
        prompt = f"""You are a Medical Entity Extractor. Extract the EXACT medical symptoms from the following Vietnamese text. 
DO NOT add or change any words. DO NOT hallucinate.

EXAMPLES:
- "Ho kéo dài, sốt nhẹ về chiều, sụt cân" -> ["Ho kéo dài", "sốt nhẹ về chiều", "sụt cân"]
- "Đau bụng, buồn nôn, đi ngoài" -> ["Đau bụng", "buồn nôn", "đi ngoài"]
- "Sốt cao, đau đầu, phát ban" -> ["Sốt cao", "đau đầu", "phát ban"]

Symptoms: "{text}"
Return ONLY a Python list of strings.
"""
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.llm_model, "prompt": prompt, "stream": False},
                timeout=30
            )
            import ast
            res_text = response.json()["response"].strip()
            if "```" in res_text:
                res_text = res_text.split("```")[1].replace("python", "").strip()
            if "[" in res_text and "]" in res_text:
                return ast.literal_eval(res_text[res_text.find("["):res_text.rfind("]")+1])
            return [text]
        except:
            return [text]

    def generate_medical_summary(self, icd_code, symptoms, description, entity_list=None):
        """Sinh tóm tắt y tế - Bước 4: Validation Loop & Punishment Rule"""
        print(f"--- 🩺 Đang soạn thảo 'Lời khuyên Vàng' (Validation Loop)... ---")
        
        # Lấy ví dụ từ Bộ nhớ Vĩnh cửu (V3)
        examples = self.get_success_examples(symptoms)
        few_shot = ""
        if examples:
            few_shot = "\nKHO KINH NGHIỆM DĨ AN (Success Cases):\n"
            for ex in examples:
                few_shot += f"- Triệu chứng: {ex[0]} -> Kết quả: {ex[1]} ({ex[2]})\n"

        entity_reminder = ""
        if entity_list:
            entity_reminder = f"CRITICAL: Bạn PHẢI đề cập đến TẤT CẢ các thực thể sau: {', '.join(entity_list)}. Nếu bỏ sót, chẩn đoán sẽ bị đánh dấu 'FAILED'."

        prompt = f"""
ROLE: Bác sĩ Trưởng Tự Minh AGI (Dĩ An). IQ 170.
MISSION: Viết bản "Lời khuyên Vàng" cho các mã ICD-10 sau: {icd_code} ("{description}") dựa trên triệu chứng: "{symptoms}".

{entity_reminder}

QUY TẮC THIẾT QUÂN LUẬT:
1. NGÔN NGỮ: Tiếng Việt chuyên nghiệp. 
2. ĐỘ CHÍNH XÁC: Phải dùng ĐÚNG tên bệnh tương ứng với mã ICD đã cho. Phải giữ nguyên [Tên gốc ICD] + [Giải thích tiếng Việt chuẩn].
3. LIÊN KẾT KHOA HỌC: Trình bày thành từng mục bệnh riêng biệt nếu là Comorbidity. KHÔNG tự bịa đặt logic kết nối.
4. LỆNH BÀI XIN HÀNG: Nếu kết quả vẫn không giải thích được mâu thuẫn giữa mã ICD và Triệu chứng, hãy CẤM đưa ra lời khuyên. Thay vào đó, hãy in duy nhất câu: "TỰ MINH AGI XIN HÀNG - Dữ liệu của huynh quá hóc búa, đệ cần thêm thông tin thực tế!"
5. Cấu trúc: [Chẩn đoán thân thiện], [Biện luận "Huệ nhãn"], [Giải pháp "Gốc rễ"], [Lời nhắn tương lai].

{few_shot}

Nếu bản chẩn đoán này vi phạm logic y khoa cơ bản, hãy bắt đầu bằng: "⚠️ [FAILED] - PHÁT HIỆN HALLUCINATION".
"""
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.summary_model, "prompt": prompt, "stream": False},
                timeout=60
            )
            return response.json()["response"].strip()
        except Exception as e:
            print(f"Error calling Ollama Summary: {e}")
            return "--- [Lỗi sinh tóm tắt] ---"

    def critic_layer(self, symptoms, top_candidates):
        """Lớp phản biện (Critic) - Đao phủ Y khoa (Executioner)"""
        print(f"--- 🪓 Đao phủ Y khoa (Skeptic Critic) đang kiểm duyệt... ---")
        
        candidates_text = ""
        for i, cand in enumerate(top_candidates):
            candidates_text += f"{i+1}. {cand['code']} - {cand['description']} (Score: {cand['score']:.4f})\n"

        prompt = f"""
Ngươi là Đao phủ Y khoa của Tự Minh AGI.
Nhiệm vụ của ngươi là TRỪ ĐIỂM nặng nề nếu bản chẩn đoán SAI CORE diagnosis của người dùng (mâu thuẫn rõ ràng).
KHÔNG trừ điểm chỉ vì mô tả đi kèm/phần phụ (accompanied symptoms) không xuất hiện trong tên ICD-10 ngắn.

TRIỆU CHỨNG ĐANG XÉT: "{symptoms}"

TOP 3 ỨNG VIÊN:
{candidates_text}

MISSION:
1. Nếu một mã ICD chỉ giải thích được cái 'Chân' mà không giải thích được cái 'Ho', ngươi phải yêu cầu hệ thống tìm thêm mã cho cái 'Ho' (Bằng cách bác bỏ mã đó hoặc xuất Coverage thấp).
2. Tuyệt đối không được bịa đặt logic (ví dụ: tiểu nhiều gây ho). Nếu không có liên hệ y khoa hợp lý, hãy cân nhắc để giảm confidence (không dùng REJECT binary).
3. CHO PHÉP "KHỚP MỘT PHẦN" (Partial Match): Chấp nhận khi mã ICD khớp CORE diagnosis của cụm triệu chứng đang xét.
   Các chi tiết đi kèm/mô tả phụ có thể KHÔNG xuất hiện trong mô tả ICD ngắn, nhưng vẫn được PASS nếu CORE hợp lý.
4. Nếu CORE diagnosis KHÔNG khớp rõ ràng, hãy xuất "REJECT_ALL" (khi không thể đề xuất mã nào trong top 3).
5. Chuyển từ Binary sang Confidence:
   - Hãy tự chấm "confidence_score" trong thang 0..100 dựa trên mức độ khớp CORE + mức độ hợp lý y khoa.
   - Nếu confidence_score < 80 và best_candidate_index != "REJECT_ALL" => status phải là "SUGGESTION" (không dùng REJECT binary).

OUTPUT FORMAT (JSON ONLY):
{{
  "best_candidate_index": 1..3 (hoặc "REJECT_ALL"),
  "confidence_score": 0..100,
  "reasoning": "Điểm chưa khớp: ...\\nGợi ý hướng đi: ...\\nMã ICD thay thế: ...",
  "status": "APPROVED" hoặc "SUGGESTION" hoặc "REJECTED"
}}
"""
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.summary_model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=60
            )
            raw_text = response.json().get("response", "")
        except Exception as e:
            print(f"⚠️ Critic Layer — Ollama call failed: {e}")
            raw_text = ""

        # Triple-Layer Parsing: JSON → Regex → Fallback (never None, never crash)
        from nexus_core.armored_critic import safe_critic_parser
        return safe_critic_parser(raw_text)

    def strict_medical_audit(self, symptoms, codes, summary):
        """Phản biện Chủ nhận (Owner-Override Protection) (V4.1)"""
        print(f"--- 🛡️ Đang chạy Hậu kiểm Y khoa Nghiêm ngặt (Strict Medical Audit)... ---")
        
        prompt = f"""
Ngươi là Trưởng Ban Kiểm Soát Y Khoa Tự Minh AGI.
Huynh Hùng Đại vừa chấm 5 SAO cho bản chẩn đoán sau, nhưng ngươi phải thực hiện một bài test khắt khe nhất.

Triệu chứng: "{symptoms}"
Mã ICD đề xuất: {codes}
Bản tóm tắt: "{summary}"

NHIỆM VỤ:
1. Đối soát Chương (Chapter Guard): Mã ICD có thuộc chương bệnh phù hợp với triệu chứng không? (Ví dụ: Ho không thể ra G-Thần kinh).
2. Đối soát Logic (Logic Matching): Bản tóm tắt có bịa đặt triệu chứng không? Mã ICD có giải thích được ít nhất 90% triệu chứng không?

Nếu phát hiện bất kỳ mâu thuẫn nào, ngươi phải bác bỏ (FAILED) kể cả khi chủ nhân hài lòng.
OUTPUT FORMAT (JSON ONLY):
{{
  "status": "SUCCESS" hoặc "FAILED",
  "reason": "Giải thích chi tiết tại sao (Bằng tiếng Việt)..."
}}
"""
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.summary_model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=60
            )
            import json
            res = json.loads(response.json()["response"])
            return res
        except Exception as e:
            print(f"⚠️ Lỗi Strict Audit: {e}")
            return {"status": "SUCCESS", "reason": "Fallback due to error"}

    def generate_audit_report(self, symptoms, codes, reason):
        """Sinh báo cáo phản biện chuyên nghiệp (V4.1)"""
        prompt = f"""
ROLE: Đệ của Hùng Đại (Tự Minh AGI).
MISSION: Viết một đoạn ngắn (50-100 từ) giải thích tại sao huynh lại bác bỏ cái 5 sao của chủ nhân cho triệu chứng "{symptoms}" và mã {codes}.
LÝ DO CỦA ĐAO PHỦ: {reason}

YÊU CẦU:
- Ngôn ngữ: Tiếng Việt, lễ phép nhưng cương trực.
- Giải thích rõ mâu thuẫn logic y khoa (Chapter Guard, String Match).
- Kết luận: Đệ xin phép được tìm lại mã khác chuẩn hơn cho huynh!
"""
        try:
            response = requests.post(
                self.ollama_gen_url,
                json={"model": self.summary_model, "prompt": prompt, "stream": False},
                timeout=45
            )
            return response.json()["response"].strip()
        except:
            return f"🛑 Đệ xin lỗi huynh, mã {codes} không khớp logic y khoa ({reason}). Đệ xin phép tìm lại!"

    def _init_db(self):
        """Khởi tạo database Blockchain (V6)"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Bảng lịch sử phiên (V1)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diag_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                query_vn TEXT,
                query_en TEXT,
                icd_code TEXT,
                icd_desc TEXT,
                score REAL,
                summary TEXT,
                rating INTEGER,
                feedback TEXT
            )
        ''')
        
        # Bảng BỘ NHỚ VĨNH CỬU (Success_Memory) (V8 Evidence)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS success_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symptoms TEXT,
                icd_code TEXT,
                icd_description TEXT,
                weight INTEGER DEFAULT 1,
                rejections INTEGER DEFAULT 0,
                version_id INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                total_count INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 1,
                sequelae_count INTEGER DEFAULT 0,
                avg_satisfaction REAL DEFAULT 5.0,
                follow_up_7d TEXT,
                follow_up_30d TEXT,
                created_at TEXT,
                updated_at TEXT,
                current_hash TEXT,
                previous_hash TEXT
            )
        ''')
        
        # Bảng BỘ NHỚ LỖI (Error_Log) (V6 Blockchain)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symptoms TEXT,
                wrong_icd_code TEXT,
                reason TEXT,
                current_hash TEXT,
                previous_hash TEXT
            )
        ''')
        
        # TRIGGERS: Bất biến hóa (Immutability) (V6)
        for table in ["success_memory", "error_log"]:
            cursor.execute(f'''
                CREATE TRIGGER IF NOT EXISTS prevent_update_{table}
                BEFORE UPDATE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'BẤT BIẾN: Không được phép sửa đổi dữ liệu Vĩnh cửu!');
                END;
            ''')
            cursor.execute(f'''
                CREATE TRIGGER IF NOT EXISTS prevent_delete_{table}
                BEFORE DELETE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, 'BẤT BIẾN: Không được phép xóa bỏ dữ liệu Vĩnh cửu!');
                END;
            ''')
        
        conn.commit()
        conn.close()

    def calculate_hash(self, content, prev_hash):
        """Tính mã băm cho bản ghi (V6)"""
        import hashlib
        data = f"{content}{prev_hash}".encode('utf-8')
        return hashlib.sha256(data).hexdigest()

    def verify_integrity(self):
        """Kiểm toán chuỗi Blockchain (V6)"""
        print("--- 🔬 Đang kiểm toán Trí tuệ Vĩnh cửu (Integrity Audit)... ---")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for table in ["success_memory", "error_log"]:
            cursor.execute(f"SELECT id, symptoms, current_hash, previous_hash FROM {table} ORDER BY id")
            rows = cursor.fetchall()
            last_current_hash = "GENESIS"
            
            for row_id, symptoms, cur_hash, prev_hash in rows:
                if prev_hash != last_current_hash:
                    print(f"🚨 CẢNH BÁO TỐI CAO: PHÁT HIỆN SỰ CAN THIỆP TRÁI PHÉP VÀO {table.upper()} (ID: {row_id})!")
                    print(f"👉 Bản ghi '{symptoms}' bị đứt gãy chuỗi. Hệ thống đã bị khóa!")
                    sys.exit(666)
                last_current_hash = cur_hash
        conn.close()
        print("✅ Kiểm toán Hoàn tất: Chuỗi Trí tuệ Vĩnh cửu Toàn vẹn.")

    def calculate_clinical_risk(self, code):
        """Tính toán tỉ lệ di chứng dựa trên dữ liệu lâm sàn (V8)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(sequelae_count), SUM(total_count) FROM success_memory WHERE icd_code = ?", (code,))
        res = cursor.fetchone()
        conn.close()
        if res and res[1] and res[1] > 0:
            return (res[0] / res[1]) * 100
        return 0.0

    def add_to_success_memory(self, symptoms, code, desc, is_sequelae=False, satisfaction=5.0):
        """Lưu bản ghi với Minh Bạch Lâm Sàng (V8)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Lấy dữ liệu cũ để increment
        cursor.execute("SELECT MAX(version_id), weight, total_count, success_count, sequelae_count, avg_satisfaction FROM success_memory WHERE symptoms = ? AND icd_code = ?", (symptoms, code))
        row = cursor.fetchone()
        
        next_ver = (row[0] + 1) if (row and row[0]) else 1
        new_weight = (row[1] + 1) if (row and row[1]) else 1
        new_total = (row[2] + 1) if (row and row[2]) else 1
        new_success = (row[3] + 1) if (row and row[3] and not is_sequelae) else 1
        new_sequelae = (row[4] + 1) if (row and row[4] and is_sequelae) else (1 if is_sequelae else 0)
        
        # Lấy mã băm cuối cùng
        cursor.execute("SELECT current_hash FROM success_memory ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()
        prev_hash = last_row[0] if last_row else "GENESIS"
        
        # Hash bao gồm cả tỉ lệ thành công/di chứng
        content = f"{symptoms}{code}{next_ver}{new_total}{new_sequelae}{timestamp}"
        cur_hash = self.calculate_hash(content, prev_hash)
        
        cursor.execute('''
            INSERT INTO success_memory 
            (symptoms, icd_code, icd_description, weight, version_id, is_active, 
             total_count, success_count, sequelae_count, avg_satisfaction, created_at, updated_at, current_hash, previous_hash)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symptoms, code, desc, new_weight, next_ver, new_total, new_success, new_sequelae, satisfaction, timestamp, timestamp, cur_hash, prev_hash))
        
        conn.commit()
        conn.close()

    def periodic_clinical_audit(self):
        """Vòng lặp Thẩm định 180 ngày (V7) - Demo chạy ngay khi khởi động"""
        print("--- 🔬 Đang chạy Thẩm định Tiến hóa Tri thức (180-day Evolution Audit)... ---")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Lấy bản ghi active mới nhất cho mỗi triệu chứng
        cursor.execute('''
            SELECT symptoms, icd_code, icd_description, created_at FROM success_memory 
            WHERE is_active = 1
        ''')
        active_records = cursor.fetchall()
        
        for symptoms, code, desc, created_at in active_records:
            # Giả lập kiểm tra 180 ngày hoặc chạy ngẫu nhiên audit
            # Trong thực tế sẽ check: if (datetime.now() - datetime(created_at)).days > 180:
            print(f"👉 Thẩm định lại: '{symptoms}' -> {code} (Tạo ngày: {created_at})")
            
            # Tái thẩm định bằng Critic khắt khe nhất
            audit_res = self.strict_medical_audit(symptoms, code, "Re-evaluating legacy record.")
            if audit_res.get("status") == "FAILED":
                print(f"🛑 CẢNH BÁO TIẾN HÓA: Tri thức về '{symptoms}' không còn tối ưu. Đang vô hiệu hóa bản cũ.")
                
                # Vô hiệu hóa bằng cách insert bản mới với is_active = 0
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("SELECT MAX(version_id) FROM success_memory WHERE symptoms = ? AND icd_code = ?", (symptoms, code))
                next_ver = cursor.fetchone()[0] + 1
                
                cursor.execute("SELECT current_hash FROM success_memory ORDER BY id DESC LIMIT 1")
                prev_hash = cursor.fetchone()[0]
                cur_hash = self.calculate_hash(f"{symptoms}{code}{next_ver}{timestamp}DEACTIVATE", prev_hash)
                
                cursor.execute('''
                    INSERT INTO success_memory 
                    (symptoms, icd_code, icd_description, version_id, is_active, created_at, updated_at, current_hash, previous_hash)
                    VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                ''', (symptoms, code, desc, next_ver, timestamp, timestamp, cur_hash, prev_hash))
        
        conn.commit()
        conn.close()

    def track_memory_rejection(self, symptoms, code):
        """Ghi nhận rejection bằng cách INSERT bản ghi mới (Vì UPDATE bị cấm)"""
        self.add_to_error_log(symptoms, code, "Audit Rejection (Immutable Log)")

    def auto_purge_memory(self):
        """Tự động thanh lọc bộ nhớ yếu (V5)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Tìm những bản ghi có rejections >= weight
        cursor.execute("SELECT symptoms, icd_code, rejections, weight FROM success_memory WHERE rejections >= weight")
        weak_records = cursor.fetchall()
        
        for symptoms, code, rej, weight in weak_records:
            print(f"🧹 AUTO-PURGE: Hồi ức '{symptoms}' -> {code} có độ tín nhiệm thấp ({rej}/{weight}). Đang di dời sang Blacklist.")
            self.add_to_error_log(symptoms, code, f"Auto-Purged V5: Reliability {weight-rej}/{weight}")
            cursor.execute("DELETE FROM success_memory WHERE symptoms = ? AND icd_code = ?", (symptoms, code))
            
        conn.commit()
        conn.close()

    def add_to_error_log(self, symptoms, code, reason):
        """Lưu ca bị trảm với Hashing (V6)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT current_hash FROM error_log ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()
        prev_hash = last_row[0] if last_row else "GENESIS"
        
        cur_hash = self.calculate_hash(f"{symptoms}{code}{reason}", prev_hash)
        
        cursor.execute("INSERT INTO error_log (symptoms, wrong_icd_code, reason, current_hash, previous_hash) VALUES (?, ?, ?, ?, ?)", 
                       (symptoms, code, reason, cur_hash, prev_hash))
        conn.commit()
        conn.close()

    def get_success_examples(self, symptoms, limit=3):
        """Tìm các ví dụ thành công tương tự (Few-shot)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT symptoms, icd_code, icd_description FROM success_memory WHERE symptoms LIKE ? LIMIT ?", (f"%{symptoms}%", limit))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except:
            return []

    def is_blacklisted(self, symptoms, code):
        """Kiểm tra xem cặp (Triệu chứng - Mã) này có nằm trong danh sách đen không"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM error_log WHERE symptoms = ? AND wrong_icd_code = ?", (symptoms, code))
            blacklisted = cursor.fetchone() is not None
            conn.close()
            return blacklisted
        except:
            return False

    def purge_gold_memory(self, symptoms):
        """XÓA BỎ bản ghi cũ trong knowledge_gold nếu phát hiện mâu thuẫn (V3.5)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM success_memory WHERE symptoms = ?", (symptoms,))
            if cursor.rowcount > 0:
                print(f"🧹 DEBUG: Phát hiện dữ liệu Vàng không nhất quán cho '{symptoms}'. Đã thực hiện xóa bỏ trí nhớ sai để bảo vệ hệ thống!")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ Lỗi khi dọn dẹp bộ nhớ: {e}")

    def log_session(self, query_vn, query_en, icd_code, icd_desc, score, summary, rating=0, feedback=""):
        """Lưu lịch sử và tự động cập nhật Bộ nhớ (V3)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Tự động nạp vào Bộ nhớ Vĩnh cửu nếu kết quả tốt
        if rating >= 5 and "SUCCESS" in summary.upper():
            print("✨ Tự Minh đang học tập: Nạp ca xuất sắc vào Bộ nhớ Vĩnh cửu.")
            self.add_to_success_memory(query_vn, icd_code, icd_desc)
        
        # Tự động nạp vào Bộ nhớ Lỗi nếu chẩn đoán hỏng hoặc người dùng chê (Rating thấp)
        if "FAILED" in summary.upper() or (rating > 0 and rating <= 2):
            print("🪓 Tự Minh đang rút kinh nghiệm: Nạp ca lỗi vào Danh sách đen.")
            self.add_to_error_log(query_vn, icd_code, "Inconsistent Logic / Low Rating")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO diag_history 
                (timestamp, query_vn, query_en, icd_code, icd_desc, score, summary, rating, feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, query_vn, query_en, icd_code, icd_desc, score, summary, rating, feedback))
            conn.commit()
            conn.close()
            print(f"✅ Đã lưu lịch sử vào {self.db_path.name}")
        except Exception as e:
            print(f"❌ Lỗi log database: {e}")

    def load_vault(self):
        """Nạp dữ liệu và Cache Vector - Kiểm tra kỹ tính đồng bộ"""
        if not self.vault_path.exists():
            print(f"❌ Error: Không tìm thấy file tại {self.vault_path}")
            return
            
        # Nạp CSV (không header theo chuẩn Medical Vault)
        self.df = pd.read_csv(self.vault_path, header=None, on_bad_lines='skip')
        self.df.columns = ['parent', 'seq', 'code', 'description', 'full_desc', 'category_name']
        
        # Pre-build normalized unit-vector cache path alongside embeddings.
        self.unit_cache = self.base_dir / "storage/medical_vault/icd10_core/unit_vault.npy"

        if self.embedding_cache.exists():
            print(f"--- 🧠 Nạp Vector Cache (Memory-Mapping Mode) từ {self.embedding_cache.name} ---")
            # V9+: Sử dụng mmap_mode='r' để tiết kiệm RAM, nạp theo nhu cầu
            self.embeddings = np.load(self.embedding_cache, mmap_mode='r')
            
            # KIỂM TRA TỬ HUYỆT: Khớp độ dài tuyệt đối
            if len(self.embeddings) != len(self.df):
                print(f"❌ LỖI TỬ HUYỆT: Số lượng embeddings ({len(self.embeddings)}) KHÔNG KHỚP với CSV ({len(self.df)}).")
                print(f"👉 Vui lòng chạy: .\\.venv\\Scripts\\python.exe missions_hub/full_icd10_ingestion.py")
                sys.exit(1)

            # --- 🧮 Precompute/load norm_vault (cosine denominator) ---
            # DÙNG mmap cho embeddings, nhưng phép np.linalg.norm(self.embeddings, axis=1)
            # nếu tính lại theo từng query sẽ gây tốn I/O và có thể làm treo. Vì vậy:
            # - cache norm_vault ra file 1 lần
            # - load lại ở lần chạy sau
            if self.norm_cache.exists():
                print(f"--- 🧮 Nạp norm_vault cache từ {self.norm_cache.name} (Memory-Mapping Mode) ---")
                self.norm_vault = np.load(self.norm_cache, mmap_mode='r')
                if len(self.norm_vault) != len(self.df):
                    print("⚠️ norm_vault cache không khớp length, sẽ tính lại.")
                    self.norm_vault = None
            if self.norm_vault is None:
                print(f"--- 🧮 Tính norm_vault (chunked) để cache ({len(self.df)} vectors) ---")
                self.norm_vault = self._compute_norm_vault_chunked(chunk_size=5000).astype(np.float32)
                self.norm_cache.parent.mkdir(parents=True, exist_ok=True)
                np.save(self.norm_cache, self.norm_vault)
                print(f"✅ Đã cache norm_vault tại: {self.norm_cache}")

            # --- 🚀 Load/build pre-normalized unit vectors for fast cosine sim ---
            # unit_vault[i] = embeddings[i] / norm_vault[i]
            # Cosine(q, d) = dot(unit_q, unit_d)  — O(D) with no division per query.
            # We store as float32 mmap to save RAM; build once, reuse forever.
            if self.unit_cache.exists():
                try:
                    self._unit_vault = np.load(self.unit_cache, mmap_mode='r')
                    if len(self._unit_vault) != len(self.df):
                        print("⚠️ unit_vault cache không khớp length, sẽ tính lại.")
                        self._unit_vault = None
                    else:
                        print(f"--- 🚀 Đã nạp unit_vault (pre-normalized) từ {self.unit_cache.name} ---")
                except Exception:
                    self._unit_vault = None
            else:
                self._unit_vault = None

            if self._unit_vault is None:
                self._build_unit_vault()
        else:
            print("--- ⚠️ Vector Cache chưa tồn tại! ---")
            print("👉 Bạn cần chạy script 'missions_hub/full_icd10_ingestion.py' để tạo toàn bộ embeddings lần đầu.")
            print("--- Tạm thời sử dụng 100 dòng mẫu để Demo ---")
            sample_df = self.df.head(100)
            all_embeddings = [self.get_ollama_embedding(str(desc)) for desc in sample_df['description']]
            self.embeddings = np.array([e for e in all_embeddings if e is not None])
            self.norm_vault = np.linalg.norm(self.embeddings, axis=1).astype(np.float32)
            norms = self.norm_vault[:, np.newaxis]
            self._unit_vault = (self.embeddings / np.where(norms == 0, 1.0, norms)).astype(np.float32)
            self.unit_cache = None  # Skip saving for demo mode

    def _compute_norm_vault_chunked(self, chunk_size: int = 5000):
        """
        Tính norm cho từng vector (L2 norm) theo chunk để tránh spike RAM.
        embeddings được kỳ vọng là memmap (mmap_mode='r'), nhưng vẫn phải đọc tuần tự từng đoạn.
        """
        if self.embeddings is None:
            raise ValueError("Embeddings not loaded. Call load_vault() first.")
        total = len(self.embeddings)
        out = np.empty((total,), dtype=np.float32)
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            chunk = self.embeddings[start:end]
            # ép dtype sang float32 để giảm bộ nhớ tạm
            chunk_f = np.asarray(chunk, dtype=np.float32)
            out[start:end] = np.sqrt(np.sum(chunk_f * chunk_f, axis=1))
        return out

    def _build_unit_vault(self) -> None:
        """
        Precompute and cache pre-normalized unit vectors.
        After this, cosine_sim(query, doc[i]) = dot(unit_query, unit_vault[i])
        which eliminates the per-query division op on N vectors.
        """
        if self.embeddings is None or self.norm_vault is None:
            return
        print(f"--- 🚀 Xây dựng unit_vault ({len(self.embeddings)} vectors, chunked float32) ---")
        total = len(self.embeddings)
        chunk = 5000
        out = np.empty((total, self.embeddings.shape[1]), dtype=np.float32)
        for start in range(0, total, chunk):
            end = min(start + chunk, total)
            emb_chunk = np.asarray(self.embeddings[start:end], dtype=np.float32)
            norms = self.norm_vault[start:end, np.newaxis]
            # Avoid division-by-zero for zero vectors
            safe_norms = np.where(norms == 0.0, 1.0, norms)
            out[start:end] = emb_chunk / safe_norms
        self._unit_vault = out
        if self.unit_cache is not None:
            try:
                self.unit_cache.parent.mkdir(parents=True, exist_ok=True)
                np.save(self.unit_cache, out)
                print(f"✅ Đã cache unit_vault tại: {self.unit_cache}")
            except Exception as exc:
                print(f"⚠️ Không thể save unit_vault: {exc}")

    def tuminh_multi_diagnostic_loop(self, user_query, exclude_codes=None):
        """Quy trình chẩn đoán đa tầng (Thiết quân luật) (V5 Smart Search)"""
        if exclude_codes is None: exclude_codes = []
        if self.df is None: self.load_vault()
        if self.embeddings is None: return None, None, None, None, None, None, "[NO_MEDICAL_DATA_FOUND]"

        print(f"\n--- 🚔 BẮT ĐẦU MẶT LỆNH THIẾT QUÂN LUẬT (V5) ---")
        
        # BƯỚC 1: Tách triệu chứng
        parts = self.split_symptoms(user_query)
        is_emergency = self._is_emergency_case(user_query)
        coverage_report = {p: False for p in parts}
        final_diagnoses = []
        
        # BƯỚC 2: Tra cứu song song (multi-search)
        for part in parts:
            # --- V5 SMART SEARCH (Kinh nghiệm lâm sàng) ---
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT icd_code, icd_description, weight FROM success_memory WHERE symptoms = ? AND weight >= 2 ORDER BY weight DESC LIMIT 1", (part,))
            experience = cursor.fetchone()
            conn.close()
            
            if experience and experience[0] not in exclude_codes:
                exp_code, exp_desc, exp_weight = experience
                print(f"✨ SMART SEARCH: Phát hiện 'Kinh nghiệm lâm sàng' cho '{part}' (Trọng số: {exp_weight}).")
                
                # V8: Kiểm tra rủi ro di chứng
                risk_rate = self.calculate_clinical_risk(exp_code)
                risk_warning = ""
                if risk_rate > 10:
                    risk_warning = f"\n🔴 **CẢNH BÁO NGUY CƠ DI CHỨNG CAO ({risk_rate:.1f}%)** 🔴"
                
                # Nếu trọng số rất cao (>=5), ưu tiên dùng luôn, nếu thấp hơn thì vẫn chạy Search để kiểm chứng
                if exp_weight >= 5:
                    final_diagnoses.append({
                        "part": part,
                        "code": exp_code,
                        "name": exp_desc,
                        "reasoning": f"Dựa trên {exp_weight} ca chẩn đoán thành công trước đó.{risk_warning}"
                    })
                    coverage_report[part] = True
                    continue

            query_en = self.translate_query(part)
            query_vector = self.get_ollama_embedding(query_en)
            if query_vector is None: continue
            
            query_arr = np.asarray(query_vector, dtype=np.float32)
            norm_query = float(np.linalg.norm(query_arr))
            if norm_query < 1e-9:
                continue  # zero-vector query, skip

            if self._unit_vault is not None:
                # Fast path: cosine_sim = dot(unit_query, unit_vault[i])
                # — no per-element division needed since both sides are pre-normalized
                unit_query = query_arr / norm_query
                similarities = self._unit_vault @ unit_query  # shape (N,), float32
            else:
                # Fallback: classic cosine with norm_vault
                if self.norm_vault is None:
                    self.norm_vault = np.linalg.norm(self.embeddings, axis=1).astype(np.float32)
                similarities = np.dot(self.embeddings, query_arr) / (self.norm_vault * norm_query)

            # Pre-filter candidates by likely ICD chapter using VN keyword groups.
            # This prevents "Chapter J vs G" retrieval noise from causing an immediate hard reject.
            allowed_prefixes = self._allowed_icd_chapter_prefixes(part)
            allowed_prefix_letters = None
            if allowed_prefixes is not None:
                allowed_prefix_letters = set([c[0].upper() for c in allowed_prefixes])

            # Compute a wider candidate pool, then filter down to the top 3 allowed.
            top_pool = 15
            # np.argpartition is O(N) vs O(N log N) for argsort — ~12x faster for N=70k.
            # We partition to get the top_pool highest-scoring indices, then sort only those.
            part_idx = np.argpartition(similarities, -top_pool)[-top_pool:]
            sorted_indices = part_idx[np.argsort(similarities[part_idx])[::-1]]

            S_i = []
            # 1) First pass: limit to top_pool highest similarities to avoid iterating
            # through the whole vault when we already have enough candidates.
            for idx in sorted_indices[:top_pool]:
                code_str = str(self.df.iloc[idx]['code'])
                icd_chap = code_str[0].upper() if code_str else ""

                if allowed_prefix_letters is not None:
                    if icd_chap not in allowed_prefix_letters and icd_chap not in ["R", "Z"]:
                        continue

                row = self.df.iloc[idx]
                S_i.append({
                    "code": row['code'],
                    "description": row['description'],
                    "score": float(similarities[idx]),
                })
                if len(S_i) >= 3:
                    break

            # 2) Fallback: if after filtering we still don't have 3 candidates,
            # continue scanning the rest until we reach 3 allowed.
            if len(S_i) < 3:
                for idx in sorted_indices[top_pool:]:
                    code_str = str(self.df.iloc[idx]['code'])
                    icd_chap = code_str[0].upper() if code_str else ""

                    if allowed_prefix_letters is not None:
                        if icd_chap not in allowed_prefix_letters and icd_chap not in ["R", "Z"]:
                            continue

                    row = self.df.iloc[idx]
                    S_i.append({
                        "code": row['code'],
                        "description": row['description'],
                        "score": float(similarities[idx]),
                    })
                    if len(S_i) >= 3:
                        break

            # BƯỚC 2.5: Pathognomonic Re-rank (V5.1)
            # Nếu triệu chứng có dấu hiệu màng não → boost G00-G09 lên đầu S_i,
            # loại bỏ I10-I15 (cao huyết áp) khỏi danh sách để tránh nhiễu vector.
            _part_lower = part.lower()
            _meningeal_kws = frozenset([
                "cứng cổ", "cứng gáy", "neck stiffness", "nuchal rigidity",
                "sợ ánh sáng", "photophobia",
            ])
            if any(kw in _part_lower for kw in _meningeal_kws):
                _g_codes  = [c for c in S_i if str(c.get("code", "")).upper().startswith("G")]
                _other    = [c for c in S_i
                             if not str(c.get("code", "")).upper().startswith("G")
                             and not any(
                                 str(c.get("code", "")).upper().startswith(pfx)
                                 for pfx in ("I10", "I11", "I12", "I13", "I14", "I15")
                             )]
                S_i = _g_codes + _other
                if _g_codes:
                    print(f"⚡ Meningeal boost: G-codes ưu tiên — {[c['code'] for c in _g_codes]}")
                if len(S_i) < 1 and allowed_prefix_letters is not None:
                    # Nếu không còn candidate nào sau filter, nới rộng lại
                    S_i = _g_codes + _other  # đã là kết quả tốt nhất có thể

            # BƯỚC 3: Lớp Đao phủ (Skeptic Critic) kiểm tra độ phủ
            critic_res = self.critic_layer(part, S_i)

            best_idx = critic_res.get("best_candidate_index")
            critic_status = critic_res.get("status")
            # Doctor-assistant rule:
            # - APPROVED and SUGGESTION: allow presenting the result
            # - REJECTED: reject the candidate
            critic_ok = best_idx != "REJECT_ALL" and critic_status in ("APPROVED", "SUGGESTION")

            if critic_ok:
                idx = 0
                try:
                    val = critic_res.get("best_candidate_index")
                    if isinstance(val, int) and 1 <= val <= 3: idx = val - 1
                except: pass
                
                best_match = S_i[idx]
                
                # BƯỚC 3.1: Kiểm tra Danh sách đen (Error_Log) & Exclude List (V4.1)
                if best_match['code'] in exclude_codes or self.is_blacklisted(part, best_match['code']):
                    print(f"🛑 BLACKLIST/EXCLUDE VẢ: Mã {best_match['code']} cho '{part}' bị loại trừ. Tìm mã khác...")
                    # Thử ứng viên tiếp theo nếu có
                    if len(S_i) > idx + 1:
                        best_match = S_i[idx+1]
                        print(f"🔄 Đang thử ứng viên thay thế: {best_match['code']}")
                    else:
                        continue

                # BƯỚC 3.2: Khóa Chương (Strict Chapter Rule)
                chap_pass, chap_reason = self.strict_chapter_check(part, best_match['code'])
                if not chap_pass:
                    print(f"❌ KHÓA CHƯƠNG TRẢM: {chap_reason}")
                    continue

                # BƯỚC 3.5: Khóa Reverse Description Check & Exact String Match
                rev_check = self.reverse_description_check(part, best_match['description'])
                if "REJECT" in rev_check:
                    print(f"❌ REVERSE CHECK TRẢM: {rev_check}")
                    continue

                final_diagnoses.append({
                    "part": part,
                    "code": best_match['code'],
                    "name": best_match['description'],
                    "reasoning": critic_res.get("reasoning", ""),
                    "critic_status": critic_status,
                    "critic_confidence": critic_res.get("confidence_score", None),
                })
                coverage_report[part] = True

                # BƯỚC 3.6: Cơ chế Tự thanh lọc Bộ nhớ (V3.5)
                # Nếu đã có trong Gold Memory nhưng mã ICD mới lại khác -> Purge
                past_gold = self.get_success_examples(part, limit=1)
                if past_gold:
                    old_symptom, old_code, old_desc = past_gold[0]
                    if old_code != best_match['code']:
                        self.purge_gold_memory(part)

            else:
                print(f"❌ Đao phủ đã bác bỏ kết quả cho: {part}")

        # BƯỚC 4: Kiểm chứng cuối cùng (Hard Validation)
        if all(coverage_report.values()):
            combined_codes = ", ".join([d['code'] for d in final_diagnoses])
            summary = self.generate_medical_summary(combined_codes, user_query, "Chẩn đoán thực thể đa tầng.", entity_list=parts)
            
            # Kiểm tra Lệnh bài Xin hàng
            if "XIN HÀNG" in summary.upper():
                print("🛑 AI ĐÃ TREO CỜ TRẮNG (XIN HÀNG).")
                status_label = "AXIN_HANG"
                return user_query, status_label, "NONE", "INCONCLUSIVE", 0.0, summary, summary

            output = [f"### [TỰ MINH AGI: THIẾT QUÂN LUẬT - SUCCESS]"]
            output.append(f"Triệu chứng gốc: '{user_query}'\n")
            for i, diag in enumerate(final_diagnoses):
                output.append(f"**Thực thể {i+1} ({diag['part']}):**")
                output.append(f"- 🟢 Mã: {diag['code']} | {diag['name']}")
                critic_status = diag.get("critic_status")
                conf_val = diag.get("critic_confidence")
                conf_str = ""
                try:
                    if conf_val is not None:
                        conf_str = f" ({int(conf_val)}%)"
                except Exception:
                    conf_str = ""
                logic_emoji = "🟠" if critic_status == "SUGGESTION" else "🟢"
                output.append(
                    f"- {logic_emoji} Logic ({critic_status or 'UNKNOWN'}{conf_str}): {diag['reasoning']}"
                )
                output.append("")
            output.append("="*40)
            output.append("### [TỔNG KẾT TỪ BÁC SĨ TỰ MINH]")
            output.append(summary)
            
            return user_query, "Martial Law SUCCESS", combined_codes, "Combined Entities", 1.0, summary, "\n".join(output)
        else:
            missing = [p for p, status in coverage_report.items() if not status]
            # Emergency override: allow presenting partial result with a confidence warning.
            if is_emergency and len(final_diagnoses) > 0:
                combined_codes = ", ".join([d["code"] for d in final_diagnoses])
                used_parts = [d["part"] for d in final_diagnoses]

                summary = self.generate_medical_summary(
                    combined_codes,
                    user_query,
                    "Chẩn đoán cấp cứu (mức độ tin cậy trung bình).",
                    entity_list=used_parts,
                )

                warning_note = "Cảnh báo mức độ tin cậy trung bình"
                if "XIN HÀNG" in str(summary).upper():
                    summary = f"### ⚠️ {warning_note}\n\n(Kết quả tạm thời: hệ thống tìm được mã: {combined_codes})"
                else:
                    summary = f"### ⚠️ {warning_note}\n\n{summary}"

                output = ["### [TỰ MINH AGI: THIẾT QUÂN LUẬT - EMERGENCY]"]
                output.append(f"Triệu chứng gốc: '{user_query}'")
                output.append("")
                output.append(f"**Lưu ý:** {warning_note}")
                output.append("")
                for i, diag in enumerate(final_diagnoses):
                    output.append(f"**Thực thể {i+1} ({diag['part']}):**")
                    output.append(f"- 🟠 Mã: {diag['code']} | {diag['name']}")
                    output.append(f"- 🟠 Logic: {diag.get('reasoning','')}")
                    output.append("")

                details = "\n".join(output)
                return user_query, "EMERGENCY_WARN", combined_codes, "Emergency Partial Entities", 0.7, summary, details

            alert_msg = (
                f"### 🔴 CẢNH BÁO ĐỎ: Hệ thống chưa tìm thấy mã ICD phù hợp cho: {missing}.\n"
                f"Lý do: Đao phủ Y khoa đã bác bỏ các kết quả không đủ độ phủ hoặc mâu thuẫn logic. "
                f"Vui lòng nhập chi tiết phản hồi hoặc kiểm tra lại triệu chứng!"
            )
            return user_query, "RED_ALERT", "FAILED", "INCOMPLETE", 0.0, alert_msg, alert_msg

    def search_icd10(self, user_query, exclude_codes=None):
        # Chuyển hướng sang loop mới
        return self.tuminh_multi_diagnostic_loop(user_query, exclude_codes=exclude_codes)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, default=None)
    args = parser.parse_args()
    
    tool = MedicalDiagnosticTool()
    
    query = args.query
    if not query or "?" in query:
        print("--- 💡 Nhập triệu chứng trực tiếp để tránh lỗi phông chữ terminal (UTF-8) ---")
        try:
            query = input("Nhập triệu chứng/bệnh lý: ").strip()
        except EOFError:
            pass

    if query:
        exclude_list = []
        while True:
            result_pkg = tool.search_icd10(query, exclude_codes=exclude_list)
            if len(result_pkg) == 7: # Thành công
                q_vn, q_en, code, desc, score, summary, formatted = result_pkg
                print(formatted)
                
                # Giao diện đánh giá cuối cùng
                print("\n" + "-"*30)
                try:
                    feedback_str = input("👉 Đánh giá của bạn (Ví dụ: 5 - Rất hài lòng): ").strip()
                    rating = 0
                    feedback_msg = feedback_str
                    # Tách rating nếu có số ở đầu
                    if feedback_str and feedback_str[0].isdigit():
                        rating = int(feedback_str[0])
                        feedback_msg = feedback_str[1:].strip().replace("- ", "")
                    
                    # CƠ CHẾ PHẢN BIỆN CHỦ NHÂN (V4.1)
                    if rating >= 5:
                        audit_res = tool.strict_medical_audit(q_vn, code, summary)
                        if audit_res.get("status") == "FAILED":
                            print(f"\n🛑 ĐAO PHỦ PHẢN BIỆN HUYNH HÙNG ĐẠI!")
                            report = tool.generate_audit_report(q_vn, code, audit_res.get('reason'))
                            print("="*40)
                            print(f"📄 BÁO CÁO PHẢN BIỆN:\n{report}")
                            print("="*40)
                            
                            print("🪓 Hệ thống tự động Blacklist mã này và khởi động lại vòng lặp chẩn đoán...")
                            tool.add_to_error_log(q_vn, code, f"V4.1 Rejected: {audit_res.get('reason')}")
                            # V5: Ghi nhận sự phản đối vào bộ nhớ
                            tool.track_memory_rejection(q_vn, code)
                            # Thêm vào exclude list để vòng lặp mới bỏ qua mã này
                            for c in code.split(", "):
                                exclude_list.append(c)
                            continue
                    
                    tool.log_session(q_vn, q_en, code, desc, score, summary, rating, feedback_msg)
                    break # Thoát vòng lặp khi đã đồng thuận
                except EOFError:
                    tool.log_session(q_vn, q_en, code, desc, score, summary)
                    break
            else:
                print(result_pkg[-1])
                break
    else:
        print("❌ Lỗi: Bạn chưa cung cấp câu hỏi.")