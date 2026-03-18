import chromadb
import ollama
from pathlib import Path

# Path to the specialized vault
storage_path = Path("i:/TuminhAgi/storage/medical_vault/icd10_core/")
client = chromadb.PersistentClient(path=str(storage_path))
collection = client.get_collection(name="icd10_core")

# Specific Symptom Query
query = "Bệnh nhân sốt nhẹ về đêm kéo dài, sụt cân khôn rõ nguyên nhân khoảng 5kg trong 1 tháng, xuất hiện khối hạch lớn ở cổ nhưng sờ vào không thấy đau, hạch chắc và di động kém."

# Get embedding
print("Generating embedding...")
embed_res = ollama.embeddings(model="nomic-embed-text:latest", prompt=query)
embedding = embed_res['embedding']

# Search for the query
print("Searching for Case 1...")
res = collection.query(query_embeddings=[embedding], n_results=10)

print("\n--- TOP 10 SEARCH RESULTS ---")
for i in range(len(res["ids"][0])):
    print(f"RANK {i+1}: {res['ids'][0][i]} | Dist: {res['distances'][0][i]:.4f}")
    print(f"DOCUMENT: {res['documents'][0][i][:100]}...")
    print("-" * 30)

# Manually check if C81.9 exists
print("\nChecking specifically for C81.9...")
try:
    c_res = collection.get(ids=["C81.9"], include=["documents", "metadatas"])
    if c_res["ids"]:
        print(f"✅ FOUND C81.9: {c_res['documents'][0][:100]}...")
    else:
        print("❌ C81.9 NOT FOUND in DB.")
except Exception as e:
    print(f"❌ Error checking C81.9: {e}")
