"""
TuminhAGI — Eternal Memory Manager
====================================
Advanced RAG module with time-weighted decay, semantic chunking, 
and ChromaDB persistence.

Author: TuminhAGI Principal AI Architect (Enhanced by Tự Minh)
Stack: chromadb, sentence_transformers, numpy, re
"""

import os
import time
import math
import logging
import re
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from rank_bm25 import BM25Okapi
from config import (
    W_BM25, W_VECTOR, W_HUMAN, W_RECENCY, 
    TIER_VITAL, TIER_STRONG, TIER_NORMAL
)

# Logger Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - ETERNAL_MEMORY - %(levelname)s - %(message)s')
logger = logging.getLogger("EternalMemory")

class EternalMemoryManager:
    """Core memory engine with Weighted RAG (BM25 + Vector + Human + Recency)."""
    
    def __init__(self, storage_path: str = "./storage/eternal_db", 
                 model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=str(self.storage_path))
        self.collection = self.client.get_or_create_collection(
            name="eternal_memories",
            metadata={"hnsw:space": "l2"}
        )
        
        self.decay_rate = 0.05
        self._refresh_bm25()

    def _refresh_bm25(self):
        """Loads all documents from ChromaDB and initializes BM25."""
        try:
            results = self.collection.get()
            self.docs = results.get("documents", [])
            self.metadatas = results.get("metadatas", [])
            self.ids = results.get("ids", [])
            
            if self.docs:
                tokenized_corpus = [doc.lower().split() for doc in self.docs]
                self.bm25 = BM25Okapi(tokenized_corpus)
            else:
                self.bm25 = None
        except Exception as e:
            logger.error(f"BM25 Init failed: {e}")
            self.bm25 = None

    def _get_tier(self, score: int) -> str:
        if score >= TIER_VITAL: return "VITAL"
        if score >= TIER_STRONG: return "STRONG"
        if score >= TIER_NORMAL: return "NORMAL"
        return "WEAK"

    def _semantic_chunking(self, text: str, max_words: int = 50) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence: continue
            
            words = sentence.split()
            word_count = len(words)
            
            if current_word_count + word_count > max_words and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_word_count = word_count
            else:
                current_chunk.append(sentence)
                current_word_count += word_count
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    def add_memory(self, content: str, is_vital: bool = False, human_score: int = 50):
        """Encodes and saves memory with specific tier and human score."""
        if not content.strip(): return
            
        try:
            chunks = self._semantic_chunking(content)
            if not chunks: return
                
            current_time = time.time()
            embeddings = self.model.encode(chunks).tolist()
            ids = [f"mem_{int(current_time * 1000)}_{i}" for i in range(len(chunks))]
            
            # Vital override
            effective_score = 100 if is_vital else human_score
            tier = self._get_tier(effective_score)
            
            metadatas = [{
                "timestamp": current_time, 
                "vital": is_vital, 
                "human_score": effective_score,
                "tier": tier
            } for _ in chunks]
            
            self.collection.add(
                embeddings=embeddings,
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )
            self._refresh_bm25() # Update BM25 with new data
            logger.info(f"Memory Saved [{tier}]: {len(chunks)} chunks.")
        except Exception as e:
            logger.error(f"Add memory failed: {e}")

    def retrieve_memory(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieves using weighted formula: BM25 + Vector + Human + Recency."""
        if not self.bm25: return []
            
        try:
            current_time = time.time()
            
            # A. BM25 Scoring
            tokenized_query = query.lower().split()
            bm25_raw_scores = self.bm25.get_scores(tokenized_query)
            max_bm25 = max(bm25_raw_scores) if max(bm25_raw_scores) > 0 else 1.0
            norm_bm25 = [s / max_bm25 for s in bm25_raw_scores]

            # B. Vector Scoring (ChromaDB)
            query_embedding = self.model.encode([query]).tolist()
            # Fetch semi-large candidate pool for re-ranking
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=min(len(self.docs), k * 5)
            )
            
            if not results or not results['ids'] or not results['ids'][0]:
                return []

            # Mapping distance to similarity for query results
            id_to_vec_sim = {}
            max_dist = max(results['distances'][0]) if results['distances'][0] else 1.0
            for i in range(len(results['ids'][0])):
                dist = results['distances'][0][i]
                sim = 1.0 - (dist / max_dist) if max_dist > 0 else 0.5
                id_to_vec_sim[results['ids'][0][i]] = sim

            # C. Final Aggregation & Weighting
            # We iterate over the candidate pool to apply weights
            scored_memories = []
            
            # For each document in the FULL collection (to include BM25)
            # Optimization: Only score candidates from BM25 top or Vector top
            candidate_ids = set(results['ids'][0])
            
            for index, mem_id in enumerate(self.ids):
                # 1. BM25 Part
                s_bm25 = norm_bm25[index]
                
                # 2. Vector Part (only if in top results, else 0)
                s_vector = id_to_vec_sim.get(mem_id, 0.0)
                
                # 3. Metadata Part
                meta = self.metadatas[index]
                h_score = meta.get("human_score", 50) / 100.0
                ts = meta.get("timestamp", current_time)
                
                # 4. Recency Part
                age_days = (current_time - ts) / 86400.0
                s_recency = math.exp(-self.decay_rate * age_days)
                
                # 5. WEIGHTED FORMULA (V2 Blueprint)
                # Ensure scores are within 0-1 range before weighting
                raw_score = (s_bm25 * W_BM25) + \
                            (s_vector * W_VECTOR) + \
                            (h_score * W_HUMAN) + \
                            (s_recency * W_RECENCY)
                
                # Boost if Vital (Tier-based boost)
                if meta.get("vital"):
                    raw_score *= 1.5
                
                # Convert to 0-100 Scale
                final_score = min(100, int(raw_score * 100))

                # 6. Filter Faint Memories (Score < 30)
                if final_score < 30:
                    continue

                scored_memories.append({
                    "content": self.docs[index],
                    "score": final_score,
                    "metadata": meta,
                    "tier": self._get_tier(final_score)
                })

            scored_memories.sort(key=lambda x: x["score"], reverse=True)
            return scored_memories[:k]

        except Exception as e:
            logger.error(f"Retrieval crash: {e}")
            return []

if __name__ == "__main__":
    # Internal Testing
    manager = EternalMemoryManager()
    manager.add_memory("Hùng Đại là người sáng lập và đối tác bất di bất dịch của Tự Minh.", is_vital=True)
    manager.add_memory("Tâm tốt là nền tảng của mọi hành động. Trí sáng giúp ta tiến xa hơn.", is_vital=False)
    
    time.sleep(1) # Simulation
    
    results = manager.retrieve_memory("Ai sáng lập Tự Minh?")
    print("\n--- Search Results ---")
    for res in results:
        v_tag = "[VITAL]" if res['metadata'].get('vital') else ""
        print(f"Score: {res['score']:.4f} {v_tag} | Content: {res['content']}")