import sys
import json
import csv
import time
from pathlib import Path

# Thêm project root vào path để import các module nexus_core
sys.path.append(str(Path(__file__).parent.parent))

from nexus_core.eternal_memory import EternalMemoryManager

class DiseaseKnowledgeLoader:
    """
    Medical Data Engineer Agent: Ingests curated disease knowledge 
    into TuminhAGI's Eternal Memory (storage/eternal_db).
    """
    def __init__(self):
        # EternalMemoryManager mặc định trỏ vào storage/eternal_db
        self.eternal = EternalMemoryManager()

    def ingest_icd_dataset(self, file_path: str):
        """
        Nạp dữ liệu từ JSON hoặc CSV, bóc tách và đẩy vào VectorDB + BM25.
        """
        path = Path(file_path)
        if not path.exists():
            print(f"❌ Error: File {file_path} không tồn tại.")
            return

        print(f"🚀 --- [STARTING INGESTION: {path.name}] ---")
        
        data = []
        try:
            if path.suffix.lower() == '.json':
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif path.suffix.lower() == '.csv':
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            else:
                print(f"⚠️ Unsupported format: {path.suffix}")
                return
        except Exception as e:
            print(f"🔥 Critical file read error: {e}")
            return

        success_count = 0
        error_count = 0

        for idx, entry in enumerate(data):
            try:
                # 1. Bóc tách dữ liệu (Data Parsing) với cơ chế fallback
                code = entry.get('Disease_Code', entry.get('code', 'N/A')).strip()
                name = entry.get('Disease_Name', entry.get('name', 'N/A')).strip()
                symptoms = entry.get('Symptoms', entry.get('symptoms', 'N/A')).strip()
                treatment = entry.get('Basic_Treatment', entry.get('treatment', 'N/A')).strip()

                if code == 'N/A' and name == 'N/A':
                    raise ValueError(f"Entry {idx} thiếu định danh bệnh lý (Code/Name).")

                # 2. Xây dựng cấu trúc Ingest (Hybrid Content)
                # Mã bệnh và Tên bệnh phục vụ BM25, Triệu chứng phục vụ Vector Search
                content = (
                    f"ICD_CODE: {code}\n"
                    f"DISEASE: {name}\n"
                    f"SYMPTOMS: {symptoms}\n"
                    f"TREATMENT: {treatment}\n"
                    f"[TOPIC: GENERAL_MEDICINE]"
                )

                # 3. Đẩy vào Eternal DB với cơ chế Hybrid (Vector + BM25)
                # Tier: STRONG (Score = 70) để bypass các kiến thức Normal
                self.eternal.add_memory(
                    content=content, 
                    is_vital=False, 
                    human_score=70 
                )
                
                print(f"✅ [{success_count+1}] Ingested: {code} - {name}")
                success_count += 1

            except Exception as e:
                # Cơ chế Catch-all để không làm gián đoạn tiến trình
                print(f"⚠️ Skip entry {idx} do lỗi: {e}")
                error_count += 1

        print(f"\n✨ --- [DATA INGESTION COMPLETE] ---")
        print(f"📊 Success: {success_count} | Errors: {error_count}")
        print(f"📂 Location: storage/eternal_db")

if __name__ == "__main__":
    loader = DiseaseKnowledgeLoader()
    
    # Nếu không có tham số, tạo file test nhanh và nạp
    if len(sys.argv) < 2:
        test_path = Path("i:/TuminhAgi/storage/icd_sample.json")
        sample_data = [
            {
                "Disease_Code": "J01.0",
                "Disease_Name": "Acute maxillary sinusitis",
                "Symptoms": "Pain in the cheek, headache, nasal congestion, fever.",
                "Basic_Treatment": "Antibiotics (if bacterial), decongestants, saline nasal spray."
            },
            {
                "Disease_Code": "G43.0",
                "Disease_Name": "Migraine without aura",
                "Symptoms": "Pulsating headache, nausea, sensitivity to light/sound.",
                "Basic_Treatment": "Pain relief (NSAIDs), triptans, resting in a dark room."
            }
        ]
        with open(test_path, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, indent=4)
        loader.ingest_icd_dataset(str(test_path))
    else:
        loader.ingest_icd_dataset(sys.argv[1])
