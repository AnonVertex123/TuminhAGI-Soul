import sys
import os
import requests
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import time
import io

# Thêm project root vào path để import các module nexus_core
sys.path.append(str(Path(__file__).parent.parent))

from nexus_core.eternal_memory import EternalMemoryManager

class ICD10CatalogScaler:
    """
    Scale-up Agent: Downloads and ingests thousands of ICD-10 records.
    """
    # Nguồn dữ liệu ổn định từ k4m1113 (CSV chuẩn)
    DATASET_URL = "https://raw.githubusercontent.com/k4m1113/ICD-10-CSV/master/codes.csv"
    RAW_DATA_DIR = Path("i:/TuminhAgi/storage/raw_med")

    def __init__(self):
        self.eternal = EternalMemoryManager()
        self.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.local_file = self.RAW_DATA_DIR / "icd10_global_catalog.csv"

    def download_dataset(self):
        """Tải xuống bộ dữ liệu ICD-10."""
        print(f"🌐 [DOWNLOAD] Đang kết nối tới nguồn dữ liệu ICD-10...")
        try:
            response = requests.get(self.DATASET_URL, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with open(self.local_file, "wb") as f, tqdm(
                desc="Downloading ICD-10",
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=1024):
                    size = f.write(chunk)
                    bar.update(size)
            print(f"✅ Download complete: {self.local_file}")
            return True
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False

    def scale_ingestion(self):
        """Batch processing entries into Eternal Memory."""
        if not self.local_file.exists():
            if not self.download_dataset():
                return

        print(f"📑 [PROCESS] Đang nạp dữ liệu vào Eternal DB...")
        try:
            # Tự động detect separator
            try:
                df = pd.read_csv(self.local_file, on_bad_lines='skip')
            except:
                df = pd.read_csv(self.local_file, sep=';', on_bad_lines='skip')
                
            df = df.dropna(subset=df.columns[:2]) 
            
            # Mapping cột linh hoạt
            col_map = {c.lower(): c for c in df.columns}
            code_col = col_map.get('code', df.columns[0])
            desc_col = col_map.get('description', col_map.get('desc', df.columns[1]))

            total_records = len(df)
            print(f"🚀 Tổng số bản ghi: {total_records}")

            # Scale-up: Nạp 100 bản ghi làm mẫu (theo yêu cầu demo nhanh)
            # Hùng Đại có thể tăng số này lên để nạp toàn bộ
            batch_limit = 100 
            records = df.head(batch_limit)

            with tqdm(total=len(records), desc="Scaling Ingestion") as pbar:
                for _, row in records.iterrows():
                    try:
                        code = str(row[code_col]).strip()
                        desc = str(row[desc_col]).strip()
                        
                        # Ingest với Hybrid Search support
                        content = f"ICD10: {code}\nDISEASE: {desc}\n[TAG: GENERAL_MEDICINE]"
                        
                        self.eternal.add_memory(
                            content=content,
                            is_vital=False,
                            human_score=70 # Tier: STRONG
                        )
                    except Exception:
                        pass
                    pbar.update(1)

            print(f"\n✨ --- [SCALING COMPLETE] ---")
            print(f"📊 Processed: {len(records)} items")
            print(f"📂 Eternal DB updated at storage/eternal_db")

        except Exception as e:
            print(f"🔥 Error: {e}")

if __name__ == "__main__":
    scaler = ICD10CatalogScaler()
    scaler.scale_ingestion()
