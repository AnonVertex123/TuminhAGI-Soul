"""
Hard medical symptom dictionary for Vietnamese -> English translation.

Mục tiêu:
- Giảm lỗi dịch nghiêm trọng (ví dụ: "tiểu gắt" bị nhầm sang "Seizure" hoặc "Diarrhea").
- Ưu tiên các cụm triệu chứng có độ chắc cao (core symptom phrases).
"""

from __future__ import annotations

from typing import Dict, List, Union


MappingValue = Union[str, List[str]]


# Vietnamese symptom phrases -> English medical terms.
# Output terms MUST be ontology-friendly and NOT include explanations.
HARD_MEDICAL_MAPPING: Dict[str, MappingValue] = {
    # --- Urinary ---
    "tiểu buốt": "Dysuria",
    "tiểu rát": "Burning urination",
    "tiểu gắt": "Urinary urgency",
    "tiểu buốt/gắt": ["Dysuria", "Urinary urgency"],
    "tiểu dắt": "Urinary hesitancy",
    "tiểu khó": "Difficult urination",
    "tiểu dở": "Urinary difficulty",
    "tiểu nhiều": "Polyuria",
    "nước tiểu đục": "Cloudy urine",
    "tiểu đục": "Cloudy urine",
    "tiểu ra máu": "Hematuria",
    "tiểu máu": "Hematuria",
    "tiểu đêm": "Nocturia",
    "tiểu rắt": "Urinary frequency",
    "tiểu lắt nhắt": "Urinary frequency",
    "bí tiểu": "Urinary retention",
    "tiểu són": "Urinary incontinence",
    "bí tiểu tiện": "Urinary retention",

    # --- General fever / infection-like ---
    "sốt cao": "High fever",
    "sốt nhẹ": "Low-grade fever",
    # Common diacritic loss variants from noisy entity extraction
    "sót nhẹ": "Low-grade fever",
    "sốt nhe": "Low-grade fever",
    "sot nhẹ": "Low-grade fever",
    "sốt": "Fever",
    "sót": "Fever",
    "ớn lạnh": "Chills",
    "đau cơ toàn thân": "Myalgia",
    "đau cơ": "Myalgia",
    "đau nhức cơ": "Muscle aches",

    # --- Respiratory / ENT ---
    "ho": "Cough",
    "ho đêm": "Nocturnal cough",
    "ho không đờm": "Dry cough",
    "ho có đờm": "Cough with phlegm",
    "ho ra đờm": "Productive cough",
    "khạc đờm": "Cough with phlegm",
    "đờm nhiều": "Increased sputum",
    "đờm vàng": "Yellow sputum",
    "đờm trắng": "White sputum",
    "đờm hôi": "Foul-smelling sputum",
    "đờm đặc": "Thick sputum",
    "thở gấp": "Tachypnea",
    "thở dốc": "Shortness of breath",
    "khó thở khi nằm": "Orthopnea",
    "nghẹt mũi": "Nasal congestion",
    "tắc mũi": "Nasal congestion",
    "chảy nước mũi": "Runny nose",
    "hắt hơi liên tục": "Sneezing",
    "viêm họng": "Sore throat",
    "nuốt đau": "Odynophagia",
    "khàn giọng": "Hoarseness",
    "ho khan": "Dry cough",
    "ho có đờm": "Cough with phlegm",
    "ho kéo dài": "Persistent cough",
    "đờm xanh": "Green sputum",
    "khò khè": "Wheezing",
    "khó thở": "Shortness of breath",
    "tức ngực": "Chest tightness",
    "đau ngực": "Chest pain",
    "đau ngực trái": "Left-sided chest pain",
    "đau khi hít sâu": "Pleuritic chest pain",
    "đau ngực khi hít sâu": "Pleuritic chest pain",
    "ngạt mũi": "Nasal congestion",
    "sổ mũi": "Runny nose",
    "hắt hơi": "Sneezing",
    "đau họng": "Sore throat",
    "khàn tiếng": "Hoarseness",
    "khó nuốt": "Dysphagia",
    "vướng ở cổ họng": "Throat discomfort",
    "đau tai": "Ear pain",
    "chảy mủ tai": "Otorrhea",
    "nghe kém": "Hearing loss",
    "chảy mũi": "Runny nose",
    "phù nề họng": "Throat swelling",
    "giả mạc": "Pseudomembrane",

    # --- Neurology / neuro-ish (V5.1 expanded) ---
    "đau đầu dữ dội": "Severe headache (thunderclap headache)",
    "đau đầu đột ngột dữ dội": "Sudden severe headache (thunderclap headache, SAH)",
    "đau đầu": "Headache",
    "nhức đầu": "Headache",
    "đau nửa đầu": "Migraine (unilateral headache)",
    "migraine": "Migraine",
    "sợ ánh sáng": "Photophobia",
    "sợ tiếng động": "Phonophobia",
    "chóng mặt": "Dizziness (vertigo)",
    "choáng": "Dizziness",
    "choáng váng đứng dậy": "Orthostatic hypotension",
    "co giật": "Seizure (convulsion)",
    "động kinh": "Epilepsy (seizure disorder)",
    "tê bì": "Numbness (paresthesia)",
    "tê bì tay chân": "Peripheral numbness (paresthesia)",
    "yếu nửa người": "Hemiparesis (one-sided weakness)",
    "liệt nửa người": "Hemiplegia (hemiparesis, stroke)",
    "đột quỵ": "Stroke (cerebrovascular accident, CVA)",
    "méo miệng": "Facial droop (facial palsy)",
    "nói ngọng": "Slurred speech (dysarthria)",
    "mất ngôn ngữ": "Aphasia",
    "run tay": "Hand tremor",
    "cứng cổ": "Neck stiffness (meningismus, nuchal rigidity)",
    "cứng gáy": "Nuchal rigidity (neck stiffness, meningismus)",
    "cứng cơ": "Muscle stiffness (rigidity)",
    "đi lại khó khăn": "Gait difficulty (ataxia)",
    "mất điều hòa": "Ataxia",

    # --- GI / abdominal ---
    "buồn nôn": "Nausea",
    # Avoid mapping generic "nôn" because it collides with "buồn nôn".
    "nôn mửa": "Vomiting",
    "nôn ra": "Vomiting",
    "nôn ói": "Vomiting",
    "ợ hơi": "Belching",
    "ợ chua": "Acid reflux",
    "ợ nóng": "Heartburn",
    "đau thượng vị": "Epigastric pain",
    "đau vùng thượng vị": "Epigastric pain",
    "thượng vị": "Epigastric",
    "đau sau ăn": "Pain after meals",
    "đau bụng": "Abdominal pain",
    "đau quặn bụng": "Abdominal cramping",
    "đầy bụng": "Bloating",
    "chướng bụng": "Abdominal distension",
    "tiêu chảy": "Diarrhea",
    "đi ngoài phân lỏng": "Diarrhea",
    "táo bón": "Constipation",
    # --- GI / abdominal (common variants) ---
    "khó tiêu": "Indigestion",
    "đầy hơi": "Bloating",
    "xì hơi": "Flatulence",
    "cồn cào bụng": "Abdominal discomfort",
    "trào ngược": "Acid reflux",
    "trào ngược dạ dày thực quản": "GERD",
    "nóng rát thượng vị": "Epigastric burning",
    "đau quặn bụng": "Abdominal cramping",
    "đau bụng quặn": "Abdominal cramping",
    "tiêu lỏng": "Diarrhea",
    "đi ngoài lỏng": "Diarrhea",
    "phân nhầy": "Mucus in stool",
    "phân có máu": "Blood in stool",
    "đi ngoài ra máu tươi": "Hematochezia",
    "đi ngoài phân đen": "Melena",
    "táo bón kéo dài": "Constipation",
    "táo bón lâu ngày": "Constipation",
    "bón lâu": "Constipation",
    "khó đi ngoài": "Constipation",
    "phân cứng": "Hard stools",
    "rặn nhiều khi đi ngoài": "Straining during defecation",

    # --- Cardiovascular / ACS (V5.1 expanded) ---
    "hồi hộp": "Palpitations",
    "hồi hộp, tim đập nhanh": "Palpitations; Rapid heartbeat (tachycardia)",
    "tim đập nhanh": "Rapid heartbeat (tachycardia)",
    "tim đập chậm": "Bradycardia",
    "vã mồ hôi": "Diaphoresis (excessive sweating)",
    "đổ mồ hôi": "Diaphoresis",
    "đau ngực": "Chest pain (precordial pain, angina)",
    "đau ngực trái": "Chest pain, left-sided (precordial pain, angina pectoris)",
    "đau ngực phải": "Chest pain, right-sided (pleuritic pain)",
    "tức ngực": "Chest tightness (chest pressure)",
    "đau thắt ngực": "Angina pectoris (chest tightness, ischemic chest pain)",
    "cơn đau thắt ngực": "Angina attack (acute angina pectoris)",
    "đau ngực lan lên vai": "Chest pain radiating to shoulder (referred cardiac pain)",
    "đau ngực lan lên cánh tay trái": "Chest pain radiating to left arm (angina, ACS)",
    "khó thở khi gắng sức": "Exertional dyspnea (effort dyspnea)",
    "phù chân": "Leg edema (peripheral oedema)",
    "phù 2 chân": "Bilateral leg edema (peripheral oedema)",
    "phù mặt": "Facial oedema",
    "tụt huyết áp": "Hypotension",
    "huyết áp cao": "Hypertension",
    "tăng huyết áp": "Hypertension",
    "ngất xỉu": "Syncope (loss of consciousness)",
    "ngất": "Syncope",
    "choáng váng": "Pre-syncope (dizziness, lightheadedness)",

    # --- Skin / rash ---
    "ngứa": "Itching",
    "phát ban": "Skin rash",
    "mẩn ngứa": "Itchy rash",
    "mề đay": "Urticaria",
    "mụn nước": "Vesicular rash",
    "ban đỏ": "Erythematous rash",
    "ban": "Rash",
    "mẩn": "Rash",
    "mụn nước thành chùm": "Grouped vesicular rash",
    "ngứa rát": "Burning sensation",
    "sưng phù": "Swelling",

    # --- Liver / jaundice / eyes ---
    "vàng da": "Jaundice",
    "vàng mắt": "Yellow eyes",
    "chán ăn": "Anorexia",

    # --- Metabolic / endocrine ---
    "khát nước nhiều": "Polydipsia",
    "sụt cân nhanh": "Rapid weight loss",

    # --- General body / MSK ---
    "mệt mỏi": "Fatigue",
    "sưng nóng đỏ": "Swelling and erythema",
    "đau khớp": "Joint pain",
    "đau nhức khớp": "Joint pain",
    "đau nhức khớp gối": "Knee joint pain",
    "đau khớp gối": "Knee joint pain",
    "sưng khớp": "Joint swelling",
    "cứng khớp": "Joint stiffness",
    "đau lưng": "Back pain",
    "đau lưng lan xuống chân": "Back pain radiating to leg",
    "tê bì chân": "Leg numbness",
    "đau lan xuống chân": "Radiating pain to leg",

    # --- Eye / vision ---
    "thị lực giảm sút": "Decreased vision",
    "nhìn mờ": "Blurred vision",
    "đỏ mắt": "Red eyes",

    # --- ENT / other local ---
    "ù tai": "Tinnitus",

    # --- Bleeding / bruising ---
    "chảy máu cam": "Epistaxis",
    "dễ bầm tím": "Easy bruising",

    # --- Endocrine / neuro memory-like ---
    "mất ngủ": "Insomnia",
    "lo âu": "Anxiety",
    "bồn chồn": "Restlessness",
    "hay quên": "Memory impairment",
    "lạc đường": "Disorientation",

    # --- Dental ---
    "đau răng": "Toothache",
    "sưng lợi": "Gingival swelling",
    "chảy máu chân răng": "Gum bleeding",

    # --- Gynecological / obstetric ---
    "trễ kinh": "Delayed menstruation (amenorrhea)",
    "chậm kinh": "Delayed menstruation (amenorrhea)",
    "kinh nguyệt không đều": "Irregular menstruation",
    "kinh nguyệt trễ": "Delayed menstruation (amenorrhea)",
    "mất kinh": "Amenorrhea",
    "đau bụng kinh": "Dysmenorrhea (menstrual cramps)",
    "đau hạ vị": "Lower abdominal pain (pelvic pain)",
    "ra máu âm đạo bất thường": "Abnormal uterine bleeding",
    "khí hư bất thường": "Abnormal vaginal discharge (leukorrhea)",
    "ngứa âm đạo": "Vaginal pruritus",
    "đau vùng chậu": "Pelvic pain",
    "buồn nôn sáng sớm": "Morning nausea (hyperemesis)",
    "nghén": "Morning sickness (nausea gravidarum)",

    # --- Lymph / swelling ---
    "nổi hạch": "Lymphadenopathy",
    "hạch": "Lymph node enlargement",
}


# Add "time markers" mappings that are reliable and safe.
TIME_MARKERS: Dict[str, str] = {
    "buổi sáng": "in the morning",
    "trưa": "in the afternoon",
    "chiều": "in the afternoon",
    "tối": "in the evening",
    "sau ăn": "after meals",
}


def translate_vn_symptoms_hard(text: str) -> str:
    """
    Hard mapping translation.

    Returns:
      - a string like "Dysuria; Urinary urgency" if any rule matches
      - "UNKNOWN" otherwise
    """
    if text is None:
        return "UNKNOWN"

    norm = str(text).strip().lower()
    if not norm:
        return "UNKNOWN"

    # Gather mapped terms in insertion order of match scanning.
    # Match longer keys first to avoid partial overlap.
    keys_sorted = sorted(HARD_MEDICAL_MAPPING.keys(), key=len, reverse=True)

    terms: List[str] = []

    for k in keys_sorted:
        if k in norm:
            v = HARD_MEDICAL_MAPPING[k]
            if isinstance(v, str):
                candidates = [v]
            else:
                candidates = list(v)
            for c in candidates:
                c = str(c).strip()
                if c and c not in terms:
                    terms.append(c)

    # Optionally append time marker info if present.
    for vn_time, en_time in TIME_MARKERS.items():
        if vn_time in norm:
            if en_time not in terms:
                terms.append(en_time)

    # Normalize fever specificity to avoid duplicates like:
    # "sốt nhẹ" -> ["Low-grade fever", "Fever"] (because "sốt" is a substring of "sốt nhẹ")
    if "Low-grade fever" in terms and "Fever" in terms:
        terms = [t for t in terms if t != "Fever"]
    if "High fever" in terms and "Fever" in terms:
        terms = [t for t in terms if t != "Fever"]

    # Combine fever + ANY supported time marker (apply to ALL time markers, not only afternoon)
    fever_bases = ["Low-grade fever", "High fever", "Fever"]
    time_en_values = list(TIME_MARKERS.values())

    fever_present = [t for t in terms if t in fever_bases]
    fever_present_unique: List[str] = []
    for t in fever_present:
        if t not in fever_present_unique:
            fever_present_unique.append(t)

    time_terms = [t for t in terms if t in time_en_values]
    # de-dup while preserving order
    time_terms_unique: List[str] = []
    for t in time_terms:
        if t not in time_terms_unique:
            time_terms_unique.append(t)

    # If we have fever + time markers, combine them and remove the separate time marker terms.
    if fever_present_unique and time_terms_unique:
        combined: List[str] = []
        for fb in fever_present_unique:
            for tt in time_terms_unique:
                combined.append(f"{fb} {tt}")

        # Remove fever base terms and time marker terms, then add combined back.
        terms = combined + [t for t in terms if t not in fever_present_unique and t not in time_terms_unique]

    if not terms:
        return "UNKNOWN"

    return "; ".join(terms)


def mapping_term_count() -> int:
    return len(HARD_MEDICAL_MAPPING)

