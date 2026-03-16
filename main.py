#!/usr/bin/env python3
"""
TuminhAGI — Sovereign AI Orchestrator v2-Pre
Authorized by: Hùng Đại (Eric) | Partner: Tự Minh (Lucian)
Feature: Sensory Engine (Voice & Ear) Integrated
"""

import sys
import os
import subprocess
import time
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

# --- [GIÁC QUAN] ---
try:
    from tools.sensory.voice import tuminh_voice
    from tools.sensory.ear import tuminh_ear
    SENSORY_AVAILABLE = True
except ImportError:
    SENSORY_AVAILABLE = False

console = Console()
client = LLMClient()

# Trạng thái hệ thống
VOICE_ON = False
MIC_ON = False

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
        
        # PHÁT ÂM THANH NẾU BẬT
        if VOICE_ON and SENSORY_AVAILABLE:
            # Chỉ nói đoạn tóm tắt hoặc 200 ký tự đầu để tránh quá dài nếu cần
            # Ở đây ta cho nói hết nhưng có thể ngắt bằng Ctrl+C
            tuminh_voice.speak(answer)

        # XÁC NHẬN TỪ HOA TIÊU
        console.print("\n[bold green]⚓ XÁC NHẬN TỪ HÙNG ĐẠI:[/bold green]")
        console.print("[dim]  [y]: Chấp nhận | [n]: Soi lỗi | [v]: Bật/Tắt Giọng nói | [m]: Bật/Tắt Micro[/dim]")
        
        user_choice = Prompt.ask("[Duyệt]", choices=["y", "n", "exit", "v", "m"], default="y")

        if user_choice == "v":
            global VOICE_ON
            VOICE_ON = not VOICE_ON
            msg = f"Đã {'BẬT' if VOICE_ON else 'TẮT'} giọng nói."
            console.print(f"[bold magenta]{msg}[/bold magenta]")
            if VOICE_ON: tuminh_voice.speak(msg)
            continue

        if user_choice == "m":
            global MIC_ON
            MIC_ON = not MIC_ON
            console.print(f"[bold magenta]Đã {'BẬT' if MIC_ON else 'TẮT'} chế độ Micro lắng nghe.[/bold magenta]")
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
    global VOICE_ON, MIC_ON
    
    console.print(Panel.fit(
        "[bold magenta]🪷 TuminhAGI: PHIÊN BẢN TIẾN HÓA (SENSORY)[/bold magenta]\n"
        "[dim]Hệ thống Thính giác (Vosk) & Tiếng nói (Edge-TTS): Cài đặt xong[/dim]",
        subtitle="Dành riêng cho Hùng Đại"
    ))
    
    rag, vital = WeightedRAG(), VitalMemory()
    consensus_engine = ConsensusEngine()
    
    # Chào hỏi bằng giọng nói nếu khởi tạo thành công
    if SENSORY_AVAILABLE:
        welcome_msg = "Chào Hùng Đại, Tự Minh đã sẵn sàng đồng hành cùng anh."
        console.print(f"[italic magenta]({welcome_msg})[/italic magenta]")
        # Mặc định chưa bật để tránh làm phiền, nhưng sẵn sàng
        # tuminh_voice.speak(welcome_msg) 

    while True:
        try:
            if MIC_ON and SENSORY_AVAILABLE:
                user_input = tuminh_ear.listen()
                if not user_input: 
                    MIC_ON = False # Tự tắt nếu không nghe thấy gì để quay lại phím
                    continue
                console.print(f"[bold cyan]Hùng Đại (Nói):[/bold cyan] {user_input}")
            else:
                user_input = Prompt.ask("\n[bold cyan]Hùng Đại (Eric)[/bold cyan]")
            
            if not user_input.strip(): continue
            
            # Lệnh bẻ lái khẩn cấp
            if user_input.startswith("!"):
                correction = user_input[1:].strip()
                console.print(f"[bold red]🔄 HIỆU CHỈNH KHẨN CẤP: {correction}[/bold red]")
                answer = client.call("task", f"LỆNH SỬA SAI: {correction}")
                console.print(Panel(Markdown(answer), title="Tự Minh (Đã sửa)", border_style="bold red"))
                if VOICE_ON: tuminh_voice.speak(answer)
                rag.add_memory("Correction", answer, score=98)
                continue

            # Lệnh hệ thống
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd == "/exit": break
                elif cmd == "/sync": run_sync()
                elif cmd == "/voice": 
                    VOICE_ON = not VOICE_ON
                    console.print(f"[magenta]Giọng nói: {'BẬT' if VOICE_ON else 'TẮT'}[/magenta]")
                elif cmd == "/mic":
                    MIC_ON = not MIC_ON
                    console.print(f"[magenta]Micro: {'BẬT' if MIC_ON else 'TẮT'}[/magenta]")
                elif cmd == "/stats": console.print(rag.stats())
                continue

            run_pipeline(user_input, rag, vital, consensus_engine)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Hệ thống tạm nghỉ.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]System Error: {e}[/bold red]")

if __name__ == "__main__":
    main()