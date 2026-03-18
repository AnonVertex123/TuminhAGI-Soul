import sys
import json
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import chromadb
import ollama
import numpy as np

# Thêm project root vào path để import các module nexus_core
sys.path.append(str(Path(__file__).parent.parent))

try:
    from config import MODEL_EMBED
except ImportError:
    MODEL_EMBED = "nomic-embed-text:latest"

class MassICD10Ingestion:
    """
    Big Data Medical Engineer Agent: Executes mass upsert of ICD-10 data.
    """
    def __init__(self, storage_path: str = "i:/TuminhAgi/storage/medical_vault/icd10_core/"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=str(self.storage_path))
        self.collection = self.client.get_or_create_collection(
            name="icd10_core",
            metadata={"hnsw:space": "cosine"}
        )

    def process_icd_file(self, file_path: str, batch_size: int = 200):
        path = Path(file_path)
        if not path.exists():
            print(f"❌ Error: File {file_path} không tồn tại.")
            return

        print(f"🧬 [INGESTION] Bắt đầu xử lý file: {path.name} (Batch Size: {batch_size})")

        try:
            if path.suffix.lower() == '.json':
                with open(path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    df = pd.DataFrame(raw_data)
                    # Mapping cho JSON
                    col_map = {c.lower(): c for c in df.columns}
                    code_col = col_map.get('disease_code', col_map.get('code', df.columns[0]))
                    desc_col = col_map.get('disease_name', col_map.get('description', col_map.get('desc', df.columns[1])))
                    symptoms_col = col_map.get('symptoms')
                    treatment_col = col_map.get('basic_treatment')
            else:
                # Đối với CSV từ k4m1113/ICD-10-CSV, cấu trúc là: ParentCode, Seq, Code, Desc, FullDesc, Category
                # File này KHÔNG có header.
                df = pd.read_csv(path, header=None, on_bad_lines='skip')
                # Map cứng cho catalog chuyên dụng
                code_col = 2 # Cột Code chi tiết (A000)
                desc_col = 3 # Cột Description
                symptoms_col = None
                treatment_col = None
            
            df = df.dropna(subset=[code_col, desc_col])
        except Exception as e:
            print(f"🔥 Lỗi đọc file: {e}")
            import traceback
            traceback.print_exc()
            return

        print(f"📊 Phát hiện {len(df)} bản ghi. Đang tiến hành Upsert...")

        for i in tqdm(range(0, len(df), batch_size), desc="Upserting Batches"):
            batch_df = df.iloc[i:i + batch_size]
            batch_data = {}
            
            for _, row in batch_df.iterrows():
                try:
                    icd_id = str(row[code_col]).strip()
                    icd_desc = str(row[desc_col]).strip()
                    
                    # Tránh lấy nhầm cột rỗng làm ID
                    if not icd_id or icd_id == 'nan': continue

                    symptoms = str(row[symptoms_col]) if symptoms_col is not None and pd.notna(row[symptoms_col]) else "N/A"
                    treatment = str(row[treatment_col]) if treatment_col is not None and pd.notna(row[treatment_col]) else "N/A"
                    
                    # Xây dựng text giàu ý nghĩa
                    full_text = f"ICD CODE: {icd_id} | NAME: {icd_desc}"
                    if symptoms != "N/A": full_text += f" | SYMPTOMS: {symptoms}"
                    if treatment != "N/A": full_text += f" | TREATMENT: {treatment}"
                    
                    meta = {
                        "code": icd_id,
                        "name": icd_desc,
                        "topic": "GENERAL_MEDICINE",
                        "tier": "STRONG"
                    }
                    if symptoms != "N/A": meta["symptoms"] = symptoms[:500] 
                    if treatment != "N/A": meta["treatment"] = treatment[:500]

                    embed_res = ollama.embeddings(model=MODEL_EMBED, prompt=full_text)
                    
                    batch_data[icd_id] = {
                        "document": full_text,
                        "metadata": meta,
                        "embedding": embed_res['embedding']
                    }
                except Exception:
                    continue 

            if batch_data:
                self.collection.upsert(
                    ids=list(batch_data.keys()),
                    embeddings=[v["embedding"] for v in batch_data.values()],
                    documents=[v["document"] for v in batch_data.values()],
                    metadatas=[v["metadata"] for v in batch_data.values()]
                )

        print(f"\n✨ [COMPLETE] Đã nạp thành công: {path.name}")

if __name__ == "__main__":
    ingestor = MassICD10Ingestion()
    if len(sys.argv) > 1:
        ingestor.process_icd_file(sys.argv[1])
    else:
        # Test default
        ingestor.process_icd_file("i:/TuminhAgi/data/raw_med/clinical_cases.json")
