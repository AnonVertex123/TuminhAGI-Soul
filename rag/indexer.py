import os
from pathlib import Path

class DocumentIndexer:
    def __init__(self, rag):
        self.rag = rag

    def chunk_text(self, text: str, size: int = 512, overlap: int = 50) -> list[str]:
        words: list[str] = text.split()
        chunks: list[str] = []
        i: int = 0
        while i < len(words):
            end: int = i + size
            chunk = " ".join(words[i:end])
            chunks.append(chunk)
            i += (size - overlap)
        return chunks

    def index_file(self, file_path: str) -> int:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return 0
            
        text = ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except:
            return 0
            
        chunks = self.chunk_text(text)
        count: int = 0
        for chunk in chunks:
            if chunk.strip():
                # add to rag as document
                self.rag.add_memory(
                    question=f"Document snippet from {path.name}", 
                    answer=chunk,
                    score=40
                )
                count += 1
        return count

    def index_directory(self, dir_path: str) -> dict:
        path = Path(dir_path)
        stats = {}
        if not path.exists() or not path.is_dir():
            return stats
            
        exts = [".pdf", ".md", ".txt", ".py"]
        for p in path.rglob("*"):
            if p.is_file() and p.suffix in exts:
                c = self.index_file(str(p))
                stats[str(p)] = c
                
        return stats

if __name__ == "__main__":
    from nexus_core.weighted_rag import WeightedRAG
    rag = WeightedRAG()
    indexer = DocumentIndexer(rag)
    
    print("🚀 Bắt đầu index tri thức v2...")
    for domain_dir in ["docs/genomics", "docs/philosophy", "docs/finance", "docs/logic_math"]:
        print(f"📂 Đang xử lý: {domain_dir}")
        results = indexer.index_directory(domain_dir)
        for path, count in results.items():
            if count > 0:
                print(f"  ✅ {path}: {count} chunks")
    
    print("✨ Hoàn tất index.")
