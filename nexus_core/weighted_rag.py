import json
import time
import chromadb
from rank_bm25 import BM25Okapi
import ollama

from config import (
    RAG_DIR, MEM_FILE, W_BM25, W_VECTOR, W_HUMAN, W_RECENCY,
    TIER_VITAL, TIER_STRONG, TIER_NORMAL, MODEL_EMBED
)

def get_tier(score: int) -> str:
    if score >= TIER_VITAL: return "vital"
    if score >= TIER_STRONG: return "strong"
    if score >= TIER_NORMAL: return "normal"
    return "faint"

class WeightedRAG:
    def __init__(self):
        RAG_DIR.mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=str(RAG_DIR))
        self.collection = self.chroma_client.get_or_create_collection(name="tuminh_memories")
        self.memories = []
        self._load_memories()
        self._build_bm25()

    def _load_memories(self):
        if MEM_FILE.exists():
            try:
                with open(MEM_FILE, "r", encoding="utf-8") as f:
                    self.memories = json.load(f)
            except Exception:
                pass

    def _save_memories(self):
        MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MEM_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)

    def _build_bm25(self):
        if not self.memories:
            self.bm25 = None
            return
        tokenized_corpus = [doc.get("text", "").split(" ") for doc in self.memories]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def add_memory(self, question: str, answer: str, score: int = 40) -> dict:
        import uuid
        mem_id = str(uuid.uuid4())
        text = f"Q: {question}\nA: {answer}"
        tier = get_tier(score)
        
        mem_obj = {
            "id": mem_id,
            "text": text,
            "score": score,
            "tier": tier,
            "ts": time.time(),
            "reinforced": 0,
            "source": "task"
        }
        
        try:
            embed_resp = ollama.embeddings(model=MODEL_EMBED, prompt=text)
            embedding = embed_resp["embedding"]
            
            self.collection.add(
                ids=[mem_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{"tier": tier, "score": score}]
            )
        except Exception as e:
            print(f"Warning: Embedding failure. {e}")
            
        self.memories.append(mem_obj)
        self._save_memories()
        self._build_bm25()
        return mem_obj

    def retrieve(self, query: str, top_k: int = 8) -> list[dict]:
        if not self.memories:
            return []
            
        tokenized_query = query.split(" ")
        bm25_scores = self.bm25.get_scores(tokenized_query) if self.bm25 else [0] * len(self.memories)
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
        norm_bm25 = [s/max_bm25 for s in bm25_scores]
        
        distances = []
        chroma_ids = []
        try:
            embed_resp = ollama.embeddings(model=MODEL_EMBED, prompt=query)
            query_embed = embed_resp["embedding"]
            chroma_results = self.collection.query(
                query_embeddings=[query_embed],
                n_results=min(len(self.memories), top_k * 2)
            )
            distances = chroma_results["distances"][0] if chroma_results["distances"] else []
            chroma_ids = chroma_results["ids"][0] if chroma_results["ids"] else []
        except Exception:
            pass
            
        id_to_dist = {cid: dist for cid, dist in zip(chroma_ids, distances)}
        max_dist = max(distances) if distances else 1.0
        
        results = []
        current_time = time.time()
        
        for i, mem in enumerate(self.memories):
            if mem.get("tier") == "faint":
                continue
                
            bm25_score = norm_bm25[i]
            
            dist = id_to_dist.get(mem["id"], max_dist)
            vec_sim = 1.0 - (dist / max_dist) if max_dist > 0 else 0.0
            
            human_score = mem.get("score", 0) / 100.0
            
            age_days = (current_time - mem.get("ts", current_time)) / 86400
            recency = max(0.0, 1.0 - (age_days / 30.0))
            
            final_score = (bm25_score * W_BM25) + (vec_sim * W_VECTOR) + (human_score * W_HUMAN) + (recency * W_RECENCY)
            
            mem_copy = mem.copy()
            mem_copy["_search_score"] = final_score
            results.append(mem_copy)
            
        results.sort(key=lambda x: x["_search_score"], reverse=True)
        return results[:top_k]

    def reinforce(self, mem_id: str, bonus: int = 15):
        for mem in self.memories:
            if mem["id"] == mem_id:
                mem["score"] += bonus
                mem["tier"] = get_tier(mem["score"])
                mem["reinforced"] = mem.get("reinforced", 0) + 1
                self._save_memories()
                
                try:
                    self.collection.update(
                        ids=[mem_id],
                        metadatas=[{"tier": mem["tier"], "score": mem["score"]}]
                    )
                except Exception:
                    pass
                break

    def prune(self, dry_run: bool = False) -> int:
        removed_count = 0
        new_mems = []
        
        for mem in self.memories:
            if mem["tier"] != "vital":
                mem["score"] -= 5
                mem["tier"] = get_tier(mem["score"])
                
            if mem["score"] > 0 or mem["tier"] == "vital":
                new_mems.append(mem)
            else:
                removed_count += 1
                if not dry_run:
                    try:
                        self.collection.delete(ids=[mem["id"]])
                    except Exception:
                        pass
                
        if not dry_run:
            self.memories = new_mems
            self._save_memories()
            self._build_bm25()
            
        return removed_count

    def stats(self) -> dict:
        tiers = {"vital": 0, "strong": 0, "normal": 0, "faint": 0}
        total_score = 0
        for m in self.memories:
            t = m.get("tier", "faint")
            if t in tiers:
                tiers[t] += 1
            total_score += m.get("score", 0)
        
        return {
            "total": len(self.memories),
            "vital": tiers["vital"],
            "strong": tiers["strong"],
            "normal": tiers["normal"],
            "faint": tiers["faint"],
            "avg_score": total_score / len(self.memories) if self.memories else 0
        }
