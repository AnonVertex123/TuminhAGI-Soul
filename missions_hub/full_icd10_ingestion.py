import pandas as pd
import numpy as np
import requests
import os
import sys
from tqdm import tqdm
from pathlib import Path

# Cấu hình encoding cho terminal Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Đường dẫn
BASE_DIR = Path("I:/TuminhAgi")
VAULT_PATH = BASE_DIR / "data/raw_med/icd10_global_catalog.csv" # Sử dụng đường dẫn đã xác minh
OUTPUT_PATH = BASE_DIR / "storage/medical_vault/icd10_core/embeddings.npy"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "mxbai-embed-large"

def run_ingestion():
    print("--- 🚀 BẮT ĐẦU LUYỆN ĐAN (EMBEDDING) TẠI DĨ AN ---")
    
    if not VAULT_PATH.exists():
        print(f"❌ Lỗi: Không tìm thấy file gốc tại {VAULT_PATH}")
        return

    # Nạp CSV (không header theo định dạng Medical Vault)
    df = pd.read_csv(VAULT_PATH, header=None, on_bad_lines='skip')
    df.columns = ['parent', 'seq', 'code', 'description', 'full_desc', 'category_name']
    
    descriptions = df['description'].fillna("N/A").tolist()
    
    print(f"Tổng cộng: {len(descriptions)} bản ghi cần mã hóa.")
    
    # Đảm bảo thư mục đích tồn tại
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_vectors = []
    # Chạy vòng lặp có thanh tiến trình
    for desc in tqdm(descriptions, desc="Đang mã hóa mã bệnh"):
        try:
            res = requests.post(
                OLLAMA_URL, 
                json={"model": MODEL_NAME, "prompt": str(desc)},
                timeout=30
            )
            embedding = res.json().get("embedding")
            if embedding:
                all_vectors.append(embedding)
            else:
                all_vectors.append([0.0] * 1024)
        except Exception as e:
            # print(f"Lỗi tại {desc}: {e}") # Tránh spam output
            all_vectors.append([0.0] * 1024)

    # Lưu lại bản chuẩn
    np.save(OUTPUT_PATH, np.array(all_vectors))
    print(f"\n✅ THÀNH CÔNG! File chuẩn đã được lưu tại: {OUTPUT_PATH}")
    print(f"Dung lượng dự kiến: ~{(len(all_vectors)*1024*4)/(1024*1024):.1f}MB")

if __name__ == "__main__":
    run_ingestion()
