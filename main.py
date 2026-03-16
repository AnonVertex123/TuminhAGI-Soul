#!/usr/bin/env python3
"""
TuminhAGI — Sovereign AI Orchestrator v2-Pre
Authorized by: Hùng Đại (Eric) | Partner: Tự Minh (Lucian)
"""

import sys
import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

# Đảm bảo import đúng cấu trúc
sys.path.insert(0, str(Path(__file__).parent))

from config import MAX_RETRY, CONTEXT_TOP_K
from nexus_core.weighted_rag import WeightedRAG
from nexus_core.vital_memory import VitalMemory
from nexus_core.consensus import ConsensusEngine
from nexus_core.llm_client import LLMClient

console = Console()
client = LLMClient()

def run_sync():
    """Đồng bộ dữ liệu từ GitHub."""
    console.print("[bold yellow]🔄 Đang đồng bộ tri thức từ GitHub...[/bold yellow]")
    try:
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[bold green]✅ Đồng bộ thành công![/bold green]")
            console.print(f"[dim]{result.stdout}[/dim]")
        else:
            console.print(f"[bold red]❌ Lỗi đồng bộ: {result.stderr}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]💥 Lỗi thực thi git: {e}[/bold red]")

def run_pipeline(question: str, rag: WeightedRAG, vital: VitalMemory, consensus: ConsensusEngine):
    """Quy trình đa Agent tập trung."""
    retrieved = rag.retrieve(question, top_k=CONTEXT_TOP_K)
    context = vital.format_context(retrieved)
    
    for attempt in range(MAX_RETRY):
        console.print(f"\n[bold yellow]Lần suy nghĩ {attempt + 1}/{MAX_RETRY}[/bold yellow]")
        
        # BƯỚC 1: TASK AGENT
        answer = client.call("task", f"Câu hỏi: {question}", context)
        console.print(Panel(Markdown(answer), title="Tự Minh Phản hồi", border_style="cyan"))
        
        # XÁC NHẬN TỪ HOA TIÊU
        console.print("\n[bold green]⚓ XÁC NHẬN TỪ HÙNG ĐẠI:[/bold green]")
        console.print("[dim]  [y]: Chấp nhận | [n]: Yêu cầu soi lỗi | [!lệnh]: Bẻ lái | /sync: Cập nhật GitHub[/dim]")
        user_choice = Prompt.ask("[Duyệt]", choices=["y", "n", "exit", "/sync"], default="y")

        if user_choice == "/sync":
            run_sync()
            continue

        if user_choice.lower() == "y":
            rag.add_memory(question, answer, score=100)
            console.print("[bold green]✅ Đã lưu vào Tinh hoa.[/bold green]")
            return answer
        
        elif user_choice.lower() == "n":
            console.print("[bold red]🔴 Phê bình Agent (Critic) đang làm việc...[/bold red]")
            critique = client.call("critic", f"Câu hỏi: {question}\nTrả lời: {answer}")
            
            validation = client.call("validator", f"Câu hỏi: {question}\nTrả lời: {answer}\nNhận xét: {critique}", context)
            
            is_approved, confidence = consensus.check(critique, validation)
            feedback = consensus.format_feedback(critique, validation)
            console.print(Panel(feedback, title="Kết quả phản biện", border_style="yellow"))
            continue

        elif user_choice == "exit":
            sys.exit(0)
            
    return answer

def main():
    console.print(Panel.fit(
        "[bold magenta]🪷 TuminhAGI: PHIÊN BẢN TỰN HÓA v2-Pre[/bold magenta]\n"
        "[dim]Hệ thống LLMClient & Auto-Sync: Ready[/dim]",
        subtitle="Dành riêng cho Hùng Đại"
    ))
    
    rag, vital = WeightedRAG(), VitalMemory()
    consensus_engine = ConsensusEngine()
    
    # Hiển thị stats nhanh
    stats = rag.stats()
    console.print(f"[dim]📊 Trạng thái ký ức: {stats.get('total', 0)} examples ({stats.get('vital', 0)} tinh hoa)[/dim]")

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]Hùng Đại (Eric)[/bold cyan]")
            if not user_input.strip(): continue
            
            # Lệnh bẻ lái khẩn cấp
            if user_input.startswith("!"):
                correction = user_input[1:].strip()
                console.print(f"[bold red]🔄 HIỆU CHỈNH KHẨN CẤP: {correction}[/bold red]")
                answer = client.call("task", f"LỆNH SỬA SAI: {correction}")
                console.print(Panel(Markdown(answer), title="Tự Minh (Đã sửa)", border_style="bold red"))
                rag.add_memory("Correction", answer, score=98)
                continue

            # Lệnh hệ thống
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd == "/exit": break
                elif cmd == "/sync": run_sync()
                elif cmd == "/stats": console.print(rag.stats())
                elif cmd == "/prune": 
                    count = rag.prune()
                    console.print(f"[yellow]🧹 Đã dọn dẹp {count} ký ức yếu.[/yellow]")
                continue

            run_pipeline(user_input, rag, vital, consensus_engine)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Hệ thống tạm nghỉ.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]System Error: {e}[/bold red]")

if __name__ == "__main__":
    main()