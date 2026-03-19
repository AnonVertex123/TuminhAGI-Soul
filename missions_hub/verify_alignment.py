import pandas as pd
import numpy as np
import requests
from pathlib import Path

# Cấu hình
VAULT_PATH = Path("i:/TuminhAgi/data/raw_med/icd10_global_catalog.csv")
EMBED_PATH = Path("i:/TuminhAgi/storage/medical_vault/icd10_core/embeddings.npy")
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "mxbai-embed-large"

def get_embed(text):
    res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    return np.array(res.json()["embedding"])

def verify_alignment():
    df = pd.read_csv(VAULT_PATH, header=None, on_bad_lines='skip')
    df.columns = ['parent', 'seq', 'code', 'description', 'full_desc', 'category_name']
    embeddings = np.load(EMBED_PATH, mmap_mode='r')
    
    print(f"CSV size: {len(df)}")
    print(f"Embeddings size: {len(embeddings)}")
    
    # Kiểm tra dòng đầu tiên (index 0)
    idx = 0
    desc = str(df.iloc[idx]['description'])
    vector = embeddings[idx]
    real_vector = get_embed(desc)
    
    score = np.dot(vector, real_vector) / (np.linalg.norm(vector) * np.linalg.norm(real_vector))
    print(f"Index {idx} ({desc}): Cosine Similarity = {score:.6f}")

    # Kiểm tra dòng ngẫu nhiên ở giữa (ví dụ index 35000)
    idx = 35000
    if len(df) > idx:
        desc = str(df.iloc[idx]['description'])
        vector = embeddings[idx]
        real_vector = get_embed(desc)
        score = np.dot(vector, real_vector) / (np.linalg.norm(vector) * np.linalg.norm(real_vector))
        print(f"Index {idx} ({desc}): Cosine Similarity = {score:.6f}")

    # Kiểm tra dòng 69705 (Milt op...)
    idx = 69705
    if len(df) > idx:
        desc = str(df.iloc[idx]['description'])
        vector = embeddings[idx]
        real_vector = get_embed(desc)
        score = np.dot(vector, real_vector) / (np.linalg.norm(vector) * np.linalg.norm(real_vector))
        print(f"Index {idx} ({desc}): Cosine Similarity = {score:.6f}")

if __name__ == "__main__":
    verify_alignment()
