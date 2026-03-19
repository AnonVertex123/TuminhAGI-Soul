import numpy as np
import requests
import sys

# Cấu hình encoding cho terminal Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "nomic-embed-text"

def get_embed(text):
    res = requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": text})
    return np.array(res.json()["embedding"])

def cos_sim(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def test_lang_gap():
    query_vn = "Ban đỏ hình cánh bướm ở mặt, đau nhức các khớp nhỏ"
    query_en = "Butterfly rash on face, symmetrical joint pain"
    
    target_lupus = "Discoid lupus erythematosus"
    target_military = "Milt op w unintent restrict of air/airwy, civilian, init"
    
    e_vn = get_embed(query_vn)
    e_en = get_embed(query_en)
    e_lupus = get_embed(target_lupus)
    e_milt = get_embed(target_military)
    
    print(f"Query VN: '{query_vn}'")
    print(f"Query EN: '{query_en}'")
    print(f"Target Lupus: '{target_lupus}'")
    print(f"Target Milt: '{target_military}'")
    print("-" * 20)
    print(f"VN vs Lupus: {cos_sim(e_vn, e_lupus):.4f}")
    print(f"VN vs Milt:  {cos_sim(e_vn, e_milt):.4f}")
    print(f"EN vs Lupus: {cos_sim(e_en, e_lupus):.4f}")
    print(f"EN vs Milt:  {cos_sim(e_en, e_milt):.4f}")

if __name__ == "__main__":
    test_lang_gap()
