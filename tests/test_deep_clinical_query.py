import sys
import time
from pathlib import Path
import chromadb
import ollama
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Thêm project root vào path để import config và các module khác
sys.path.append(str(Path(__file__).parent.parent))

try:
    from config import MODEL_EMBED
except ImportError:
    MODEL_EMBED = "nomic-embed-text:latest"

console = Console()

class DeepClinicalTester:
    """
    Expert QA Agent: Executes Tier-S clinical diagnosis tests 
    against the massive ICD-10 Medical Vault.
    """
    def __init__(self, storage_path: str = "i:/TuminhAgi/storage/medical_vault/icd10_core/"):
        self.storage_path = Path(storage_path)
        self.client = chromadb.PersistentClient(path=str(self.storage_path))
        self.collection = self.client.get_collection(name="icd10_core")

    def query_vault(self, query: str, top_k: int = 3):
        """Thực hiện truy vấn Hybrid-like (Vector search trên Vault chuyên biệt)."""
        # Sinh embedding cho câu hỏi lâm sàng
        embed_resp = ollama.embeddings(model=MODEL_EMBED, prompt=query)
        query_vector = embed_resp["embedding"]

        # Truy vấn ChromaDB
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        return results

    def run_deep_test(self):
        console.print(Panel.fit(
            "[bold white on red]🧪 TUMINHAGI DEEP CLINICAL QUERY TEST (TIER-S)[/bold white on red]\n"
            "[dim]Đánh giá khả năng chẩn đoán xác suất cho các ca bệnh hiếm và phức tạp[/dim]"
        ))

        # 3 CA LÂM SÀNG ĐỘ KHÓ CAO
        cases = [
            {
                "id": "CASE_1",
                "title": "Ung thư hạch (Lymphoma) - Triệu chứng mập mờ",
                "query": "Bệnh nhân sốt nhẹ về đêm kéo dài, sụt cân khôn rõ nguyên nhân khoảng 5kg trong 1 tháng, xuất hiện khối hạch lớn ở cổ nhưng sờ vào không thấy đau, hạch chắc và di động kém."
            },
            {
                "id": "CASE_2",
                "title": "Bệnh tự miễn (Autoimmune - Lupus/RA)",
                "query": "Bệnh nhân nữ trẻ tuổi, đau nhức các khớp nhỏ ở bàn tay đối xứng hai bên, cứng khớp vào buổi sáng kéo dài hơn 1 tiếng. Xuất hiện ban đỏ hình cánh bướm ở mặt khi ra nắng và mệt mỏi cực độ."
            },
            {
                "id": "CASE_3",
                "title": "Rối loạn chuyển hóa di truyền (Inborn Errors of Metabolism)",
                "query": "Trẻ sơ sinh có biểu hiện nôn trớ liên tục, li bì, co giật, nước tiểu có mùi hôi lạ như mùi xi-rô phong (maple syrup) hoặc mùi chân hôi. Xét nghiệm nồng độ acid amin trong máu tăng cao."
            }
        ]

        for case in cases:
            console.print(f"\n[bold yellow]📋 {case['id']}: {case['title']}[/bold yellow]")
            console.print(f"[dim]Query:[/dim] [italic]\"{case['query']}\"[/italic]")
            
            start_time = time.time()
            res = self.query_vault(case["query"])
            latency = (time.time() - start_time) * 1000

            # Bảng kết quả chẩn đoán Top 3
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Rank", justify="center")
            table.add_column("ICD Code", style="bold green")
            table.add_column("Diagnosis / Description", ratio=2)
            table.add_column("Confidence (Dist)", justify="right")

            if res and res["ids"]:
                for idx in range(len(res["ids"][0])):
                    dist = res["distances"][0][idx]
                    # Chuyển đổi Distance thành Score (Cosine similarity ước lượng)
                    score = max(0, 1 - dist) * 100 
                    
                    table.add_row(
                        str(idx + 1),
                        res["ids"][0][idx],
                        res["documents"][0][idx][:120] + "...",
                        f"{score:.2f}%"
                    )
            
            console.print(table)
            console.print(f"[dim]⏱️ Latency: {latency:.2f}ms[/dim]")
            console.print("─" * 60)

if __name__ == "__main__":
    try:
        tester = DeepClinicalTester()
        tester.run_deep_test()
    except Exception as e:
        console.print(f"[bold red]❌ Lỗi thực thi: {e}[/bold red]")
        console.print("[yellow]Gợi ý: Đảm bảo tiến trình nạp đã tạo đủ collection và đang chạy.[/yellow]")
