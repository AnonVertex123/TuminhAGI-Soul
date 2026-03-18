import sys
from pathlib import Path
import chromadb
from collections import Counter
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

# Thêm project root vào path
sys.path.append(str(Path(__file__).parent.parent))

console = Console()

def verify_distribution():
    storage_path = Path("i:/TuminhAgi/storage/medical_vault/icd10_core/")
    if not storage_path.exists():
        console.print("[bold red]❌ Thư mục dữ liệu chuyên biệt không tồn tại.[/bold red]")
        return

    console.print(f"[bold blue]🔍 Đang kết nối tới ICD-10 Vault tại:[/bold blue] {storage_path}")
    
    try:
        client = chromadb.PersistentClient(path=str(storage_path))
        # Kiểm tra collection icd10_core (theo script nạp mass_icd10_ingestion.py)
        collection = client.get_collection(name="icd10_core")
    except Exception as e:
        console.print(f"[bold red]❌ Không thể truy cập collection: {e}[/bold red]")
        return

    total_count = collection.count()
    console.print(f"[bold green]📊 Tổng số bản ghi hiện có trong DB:[/bold green] {total_count}")

    if total_count == 0:
        console.print("[yellow]⚠️ Database hiện đang trống.[/yellow]")
        return

    console.print("[dim]Đang quét Metadata để phân tích cấu trúc nhóm bệnh... (Lưu ý: Không tải Vector để tiết kiệm RAM)[/dim]")

    # Sử dụng generator hoặc get theo batch để an toàn bộ nhớ
    batch_size = 5000
    group_counter = Counter()

    with Progress() as progress:
        task = progress.add_task("[cyan]Đang phân tích...", total=total_count)
        
        for i in range(0, total_count, batch_size):
            # Chỉ lấy IDs để cực kỳ nhẹ RAM
            results = collection.get(
                offset=i,
                limit=batch_size,
                include=[] # Chỉ lấy IDs mặc định
            )
            
            ids = results.get("ids", [])
            for code_id in ids:
                # ICD-10 prefix thường là chữ cái đầu tiên (A-Z)
                if code_id and code_id[0].isalpha():
                    prefix = code_id[0].upper()
                    group_counter[prefix] += 1
                else:
                    group_counter["Others"] += 1
            
            progress.update(task, advance=len(ids))

    # Chuẩn bị bảng thống kê Top 20 (hoặc toàn bộ các nhóm chữ cái A-Z)
    table = Table(title="[bold magenta]BÁO CÁO PHÂN BỔ NHÓM BỆNH LÝ ICD-10[/bold magenta]", show_header=True, header_style="bold cyan")
    table.add_column("STT", justify="center")
    table.add_column("Nhóm (Prefix)", style="bold yellow")
    table.add_column("Số lượng mã", justify="right", style="green")
    table.add_column("Tỷ lệ (%)", justify="right", style="dim")

    sorted_groups = sorted(group_counter.items(), key=lambda x: x[1], reverse=True)
    
    for idx, (prefix, count) in enumerate(sorted_groups[:20]):
        percentage = (count / total_count) * 100
        table.add_row(
            str(idx + 1),
            f"Nhóm {prefix}",
            format(count, ","),
            f"{percentage:.2f}%"
        )

    console.print(table)
    console.print(f"\n[dim]Hệ thống ghi nhận {len(group_counter)} tiền tố khác nhau trong danh mục y khoa.[/dim]")

if __name__ == "__main__":
    verify_distribution()
