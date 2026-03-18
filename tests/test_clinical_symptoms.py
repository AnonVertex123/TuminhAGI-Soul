import sys
import time
from pathlib import Path

# Thêm project root vào path để import các module nexus_core
sys.path.append(str(Path(__file__).parent.parent))

from nexus_core.eternal_memory import EternalMemoryManager
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def run_clinical_diagnosis_test():
    console.print(Panel.fit("[bold red]🚑 TuminhAGI Clinical Symptoms & ICD-10 Mapping Test[/bold red]\n[dim]Mô phỏng chẩn đoán triệu chứng lâm sàng dựa trên Hybrid RAG[/dim]"))
    
    # Khởi tạo Memory Manager (Đã nạp sample_diseases.json ở bước trước)
    eternal = EternalMemoryManager()
    
    # 1. Mô phỏng lời nói của bệnh nhân (Natural Language)
    patient_query = "Bác sĩ ơi, tôi tự dưng bị đau quặn cái vùng bụng ở phía dưới bên tay phải, nãy giờ buồn nôn quá mà hơi ngai ngái sốt."
    
    console.print(f"\n[bold cyan]Bệnh nhân nói:[/bold cyan] \"{patient_query}\"")
    console.print("[dim]Đang thực hiện truy xuất Hybrid (Vector Semantic + BM25)...[/dim]\n")
    
    start_time = time.time()
    # 2. Thực hiện truy vấn Hybrid RAG
    results = eternal.retrieve_memory(patient_query, k=1)
    latency = (time.time() - start_time) * 1000

    if not results:
        console.print("[bold yellow]⚠️ Không tìm thấy kết quả phù hợp trong cơ sở dữ liệu.[/bold yellow]")
        return

    top_hit = results[0]
    
    # 3. Hiển thị kết quả chi tiết
    table = Table(title="[bold green]KẾT QUẢ CHẨN ĐOÁN GỢI Ý[/bold green]", show_header=True, header_style="bold cyan")
    table.add_column("Thông số", style="dim")
    table.add_column("Giá trị", style="bold white")
    
    table.add_row("Mã ICD-10 Dự kiến", top_hit["metadata"].get("tier", "N/A")) # Tier thực tế là STRONG
    table.add_row("Điểm tin cậy (Score)", f"{top_hit['score']}/100")
    table.add_row("Thời gian xử lý", f"{latency:.2f} ms")
    
    console.print(table)
    
    # Trích xuất thông tin từ content đã format
    content = top_hit["content"]
    
    console.print(Panel(content, title="[bold red]NỘI DUNG PHÁC ĐỒ TRUY XUẤT[/bold red]", border_style="red"))
    
    # 4. Kiểm tra kỳ vọng (K35.8)
    if "K35.8" in content or "Viêm ruột thừa" in content:
        console.print("\n[bold green]✅ TEST PASSED:[/bold green] Hệ thống đã ánh xạ đúng mô tả triệu chứng sang mã [K35.8 - Viêm ruột thừa cấp].")
        console.print("[bold red]CẢNH BÁO: ĐÂY LÀ TÌNH HUỐNG CẤP CỨU NGOẠI KHOA![/bold red]")
    else:
        console.print("\n[bold red]❌ TEST FAILED:[/bold red] Hệ thống không nhận diện đúng mã bệnh kỳ vọng.")

if __name__ == "__main__":
    run_clinical_diagnosis_test()
