import sys
import json
import time
from pathlib import Path

# Thêm path để import các module từ nexus_core
sys.path.append(str(Path(__file__).parent.parent))
from nexus_core.eternal_memory import EternalMemoryManager

class MedicalOntologyLoader:
    """
    Data Agent: Ingests ICD-10 medical ontology into Eternal Memory.
    Focus: General Medicine (J00-J99 Respiratory, I00-I99 Circulatory, etc.)
    """
    def __init__(self):
        self.eternal = EternalMemoryManager()
        # Bộ dữ liệu ICD-10 mẫu (Core General Medicine)
        # Trong thực tế sẽ load từ CSV/API lớn hơn
        self.icd10_base = [
            {"code": "J01.9", "description": "Viêm xoang cấp tính (Acute sinusitis, unspecified). Triệu chứng: Nghẹt mũi, đau vùng mặt, dịch mũi đặc.", "group": "Respiratory"},
            {"code": "I10", "description": "Tăng huyết áp vô căn (Essential hypertension). Triệu chứng: Nhức đầu, hoa mắt, ù tai, mất ngủ.", "group": "Circulatory"},
            {"code": "E11.9", "description": "Đái tháo đường type 2 không biến chứng (Type 2 diabetes mellitus without complications).", "group": "Endocrine"},
            {"code": "K29.7", "description": "Viêm dạ dày, không xác định (Gastritis, unspecified). Triệu chứng: Đau thượng vị, buồn nôn, đầy hơi.", "group": "Digestive"},
            {"code": "N39.0", "description": "Nhiễm trùng đường tiết niệu, vị trí không xác định (Urinary tract infection, site not specified).", "group": "Genitourinary"},
            {"code": "G44.2", "description": "Đau đầu do căng thẳng (Tension-type headache). Triệu chứng: Đau dai dẳng, cảm giác bó chặt quanh đầu.", "group": "Nervous"},
            {"code": "M54.5", "description": "Đau lưng dưới (Low back pain).", "group": "Musculoskeletal"},
            {"code": "B34.9", "description": "Nhiễm virus, không xác định (Viral infection, unspecified). Triệu chứng: Sốt, mệt mỏi, đau nhức cơ thể.", "group": "Infectious"},
            {"code": "J06.9", "description": "Nhiễm khuẩn đường hô hấp trên cấp tính (Acute upper respiratory infection, unspecified) - Cảm lạnh.", "group": "Respiratory"},
            {"code": "R05", "description": "Ho (Cough).", "group": "Symptoms"}
        ]

    def ingest_ontology(self):
        print(f"--- [STARTING ICD-10 INGESTION: TOPIC: GENERAL_MEDICINE] ---")
        count = 0
        for item in self.icd10_base:
            # Format content để BM25 bắt được Code và Vector bắt được triệu chứng
            content = f"CODE: {item['code']} | DISEASE: {item['description']} | CATEGORY: {item['group']} [TAG: GENERAL_MEDICINE]"
            
            # Lưu vào Eternal DB (Tầng 4)
            # score=70 cho dữ liệu ontology chuẩn (Strong tier)
            self.eternal.add_memory(content, is_vital=False, human_score=75)
            print(f"Ingested: {item['code']} - {item['group']}")
            count += 1
            
        print(f"--- [INGESTION COMPLETE: {count} entries added] ---")

if __name__ == "__main__":
    loader = MedicalOntologyLoader()
    loader.ingest_ontology()
