import json
import time
import math
import uuid
import chromadb
from rank_bm25 import BM25Okapi
import ollama
from typing import List, Dict, Any, Tuple
from pathlib import Path

from config import (
    RAG_DIR, MEM_FILE, W_BM25, W_VECTOR, W_HUMAN, W_RECENCY,
    TIER_VITAL, TIER_STRONG, TIER_NORMAL, MODEL_EMBED
)

def get_tier(score: int) -> str:
    """Returns the memory tier based on score."""
    if score >= TIER_VITAL: return "vital"
    if score >= TIER_STRONG: return "strong"
    if score >= TIER_NORMAL: return "normal"
    return "faint"

class BM25Engine:
    """Keyword-based search engine using BM25 Okapi."""
    def __init__(self, corpus: List[str]):
        self.corpus = corpus
        # Tách từ cơ bản (có thể cải tiến bằng tokenizer tiếng Việt nếu cần)
        tokenized_corpus = [doc.lower().split() for doc in corpus]
        self.bm25 = BM25Okapi(tokenized_corpus) if corpus else None

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Returns top_k hits with raw BM25 scores and corpus indices."""
        if not self.bm25: return []
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        results = []
        for i, score in enumerate(scores):
            results.append({"index": i, "score": max(0.0, float(score))})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

class WeightedRAG:
    """
    Advanced RAG Module with Hybrid BM25 + Vector Search.
    Uses Reciprocal Rank Fusion (RRF) for reranking and a 4-Tier Memory formula.
    """
    def __init__(self):
        RAG_DIR.mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=str(RAG_DIR))
        self.collection = self.chroma_client.get_or_create_collection(name="tuminh_memories")
        self.memories = []
        self._load_memories()
        self.bm25_engine = None
        self._refresh_bm25()

    def _load_memories(self):
        if MEM_FILE.exists():
            try:
                with open(MEM_FILE, "r", encoding="utf-8") as f:
                    self.memories = json.load(f)
            except Exception: pass

    def _save_memories(self):
        MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MEM_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)

    def _refresh_bm25(self):
        """Update the In-Memory BM25 engine."""
        if self.memories:
            corpus = [m.get("text", "") for m in self.memories]
            self.bm25_engine = BM25Engine(corpus)
        else:
            self.bm25_engine = None

    def add_memory(self, question: str, answer: str, score: int = 40) -> dict:
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
        self._refresh_bm25()
        return mem_obj

    def hybrid_retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """Hybrid search combining Vector and BM25 using RRF."""
        if not self.memories: return []

        # 1. BM25 Search
        bm25_hits = self.bm25_engine.search(query, top_k=top_k*3) if self.bm25_engine else []
        
        # 2. Vector Search (ChromaDB)
        vector_hits = []
        try:
            embed_resp = ollama.embeddings(model=MODEL_EMBED, prompt=query)
            query_embed = embed_resp["embedding"]
            chroma_res = self.collection.query(
                query_embeddings=[query_embed],
                n_results=min(len(self.memories), top_k*3)
            )
            id_to_idx = {m["id"]: idx for idx, m in enumerate(self.memories)}
            for i, mem_id in enumerate(chroma_res["ids"][0]):
                if mem_id in id_to_idx:
                    vector_hits.append({"index": id_to_idx[mem_id], "dist": chroma_res["distances"][0][i]})
        except Exception: pass

        # 3. Reciprocal Rank Fusion (RRF)
        # score = sum(1 / (k + rank))
        rrf_scores = {}
        K_RRF = 60
        
        for rank, hit in enumerate(bm25_hits):
            idx = hit["index"]
            rrf_scores[idx] = rrf_scores.get(idx, 0) + (1.0 / (K_RRF + rank + 1))
            
        for rank, hit in enumerate(vector_hits):
            idx = hit["index"]
            rrf_scores[idx] = rrf_scores.get(idx, 0) + (1.0 / (K_RRF + rank + 1))

        if not rrf_scores: return []

        # 4. Final Scoring with RRF + Metadata
        results = []
        max_rrf = max(rrf_scores.values())
        
        for idx, rrf_val in rrf_scores.items():
            mem = self.memories[idx]
            norm_search_relevance = rrf_val / max_rrf
            
            final_score = self.calculate_final_score(mem, norm_search_relevance)
            
            # 4-Tier Filter (Score < 30 = Faint/Weak)
            if final_score < TIER_NORMAL: 
                continue
                
            res = mem.copy()
            res["_search_score"] = final_score
            res["tier"] = get_tier(final_score)
            results.append(res)

        results.sort(key=lambda x: x["_search_score"], reverse=True)
        return results[:top_k]

    def calculate_final_score(self, memory: Dict, hybrid_relevance: float) -> int:
        """
        Calculates a memory's priority based on Hybrid relevance, Human feedback, and Recency.
        Formula: (Hybrid * 0.45) + (Human * 0.30) + (Recency * 0.15) + (Reinforce * 0.10)
        """
        # A. Hybrid RRF Score (normalized)
        s_hybrid = hybrid_relevance
        
        # B. Human Confidence
        h_score = memory.get("score", 0) / 100.0
        
        # C. Recency (Time Decay)
        age_days = (time.time() - memory.get("ts", time.time())) / 86400
        s_recency = math.exp(-0.05 * age_days)
        
        # D. Reinforcement Bonus
        s_reinf = min(1.0, memory.get("reinforced", 0) / 10.0)
        
        # Integrated Score (sum = 1.0)
        final = (s_hybrid * 0.45) + (h_score * 0.30) + (s_recency * 0.15) + (s_reinf * 0.10)
        
        # Vital Tier Lock-in
        if memory.get("tier") == "vital":
            final = min(1.0, final + 0.15)
            
        return int(final * 100)

    def retrieve(self, query: str, top_k: int = 8) -> list[dict]:
        """Legacy access point — now using the Hybrid RRF Engine."""
        return self.hybrid_retrieve(query, top_k=top_k)

    def reinforce(self, mem_id: str, bonus: int = 15):
        for mem in self.memories:
            if mem["id"] == mem_id:
                mem["score"] += bonus
                mem["reinforced"] = mem.get("reinforced", 0) + 1
                mem["tier"] = get_tier(mem["score"])
                self._save_memories()
                try:
                    self.collection.update(
                        ids=[mem_id],
                        metadatas=[{"tier": mem["tier"], "score": mem["score"]}]
                    )
                except Exception: pass
                break

    def prune(self, dry_run: bool = False) -> int:
        removed = 0
        new_mems = []
        for mem in self.memories:
            if mem["tier"] != "vital":
                mem["score"] -= 5 # Decay Pulse
                mem["tier"] = get_tier(mem["score"])
                
            if mem["score"] >= 25 or mem["tier"] == "vital": 
                new_mems.append(mem)
            else:
                removed += 1
                if not dry_run:
                    try: self.collection.delete(ids=[mem["id"]])
                    except Exception: pass
        
        if not dry_run:
            self.memories = new_mems
            self._save_memories()
            self._refresh_bm25()
        return removed

    def stats(self) -> dict:
        counts = {"vital": 0, "strong": 0, "normal": 0, "faint": 0}
        for m in self.memories:
            t = m.get("tier", "faint")
            if t in counts: counts[t] += 1
        return {
            "total": len(self.memories),
            **counts,
            "avg_score": (sum(m["score"] for m in self.memories) / len(self.memories)) if self.memories else 0
        }
