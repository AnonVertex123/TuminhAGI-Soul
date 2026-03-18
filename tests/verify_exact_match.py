import chromadb
import ollama
from pathlib import Path

storage_path = Path("i:/TuminhAgi/storage/medical_vault/icd10_core/")
client = chromadb.PersistentClient(path=str(storage_path))
collection = client.get_collection(name="icd10_core")

# Get the document text of C81.9
c_res = collection.get(ids=["C81.9"], include=["documents", "metadatas"])
if not c_res["ids"]:
    print("❌ C81.9 NOT FOUND.")
    exit()

doc_text = c_res["documents"][0]
print(f"DOCUMENT TEXT: {doc_text}")

# Get embedding for THIS EXACT TEXT
print("Embedding exact text...")
embed = ollama.embeddings(model="nomic-embed-text:latest", prompt=doc_text)["embedding"]

# Query with this embedding
print("Querying with exact embedding...")
search_res = collection.query(query_embeddings=[embed], n_results=10)

print("\n--- RESULTS FOR EXACT MATCH ---")
for i in range(len(search_res["ids"][0])):
    print(f"RANK {i+1}: {search_res['ids'][0][i]} | Dist: {search_res['distances'][0][i]:.6f}")
    if search_res['ids'][0][i] == 'C81.9':
        print(">>> THIS IS THE ONE! <<<")
    print(f"DOC: {search_res['documents'][0][i][:80]}...")
