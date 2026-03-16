#!/usr/bin/env python3
"""
TuminhAGI — Sovereign AI Orchestrator
Authorized by: Hùng Đại (Eric) | Partner: Tự Minh (Lucian)
Feature: Integrated Performance Tracker & Human-in-the-Loop
"""

import sys
import time
import ollama
from pathlib import Path
from functools import wraps
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

# Đảm bảo import đúng cấu trúc thư mục nexus_core
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    PROMPTS_DIR, MODEL_TASK, MODEL_CRITIC, MODEL_VALIDATOR, 
    MAX_RETRY, MIN_CONFIDENCE, CONTEXT_TOP_K
)
from nexus_core.weighted_rag import WeightedRAG
from nexus_core.vital_memory import VitalMemory
from nexus_core.consensus import ConsensusEngine
from nexus_core.self_improve import SelfImprove

console = Console()

# --- [BỘ ĐO THỜI GIAN TINH HOA] ---
def timer_decorator(func):
    """Decorator để đo chính xác thời gian Tự Minh 'suy nghĩ'."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        duration = end_time - start_time
        console.print(f"[bold magenta]⚡ [Hệ thống]: Agent '{kwargs.get('persona', args[0])}' phản hồi trong {duration:.2f}s[/bold magenta]")
        return result
    return wrapper

@timer_decorator
def call_model(persona: str, message: str, context: str = "") -> str:
    """Gọi model AI và thực hiện 'Khoảng nghỉ Thiền' để bảo vệ RTX 3060 Ti."""
    prompt_file = PROMPTS_DIR / f"{persona}_agent.txt"
    system_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else f"Bạn là {persona} agent."
    
    models = {"task": MODEL_TASK, "data": MODEL_TASK, "critic": MODEL_CRITIC, "validator": MODEL_VALIDATOR}
    model = models.get(persona, MODEL_TASK)
        
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n[CONTEXT]\n{context}\n[/CONTEXT]"},
        {"role": "user", "content": message}
    ]
    
    try:
        # Hạ nhiệt GPU: Nghỉ 1.5s để tản nhiệt đẩy khí nóng ra ngoài
        time.sleep(1.5) 
        response = ollama.chat(model=model, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        console.print(f"[bold red]Lỗi gọi model {model}: {e}[/bold red]")
        return ""

def run_pipeline(question: str, rag: WeightedRAG, vital: VitalMemory, consensus: ConsensusEngine):
    """Quy trình đa Agent có sự phê chuẩn trực tiếp của Hùng Đại."""
    retrieved = rag.retrieve(question, top_k=CONTEXT_TOP_K)
    context = vital.format_context(retrieved)
    
    for attempt in range(MAX_RETRY):
        console.print(f"\n[bold yellow]Attempt {attempt + 1}/{MAX_RETRY}[/bold yellow]")
        
        # BƯỚC 1: TASK AGENT
        answer = call_model("task", f"Câu hỏi: {question}", context)
        console.print(Panel(Markdown(answer), title="Tự Minh Phản hồi", border_style="cyan"))
        
        # XÁC NHẬN TỪ HOA TIÊU
        console.print("\n[bold green]⚓ XÁC NHẬN TỪ HÙNG ĐẠI:[/bold green]")
        console.print("[dim]  [y]: Đúng (Lưu & Dừng) | [n]: Sai (Tự suy nghĩ lại) | [!lệnh]: Bẻ lái gấp[/dim]")
        user_choice = Prompt.ask("[Phê duyệt]", choices=["y", "n", "exit"], default="y")

        if user_choice.lower() == "y":
            rag.add_memory(question, answer, score=100)
            console.print("[bold green]✅ Đã lưu vào Tinh hoa. Pipeline kết thúc.[/bold green]")
            return answer, 1.0
        
        elif user_choice.lower() == "n":
            console.print("[bold red]🔴 Kích hoạt Critic Agent để soi lỗi...[/bold red]")
            critique_text = call_model("critic", f"Câu hỏi: {question}\nTrả lời: {answer}")
            
            val_msg = f"Câu hỏi: {question}\nTrả lời: {answer}\nNhận xét: {critique_text}"
            validation_text = call_model("validator", val_msg, context)
            
            is_approved, confidence = consensus.check(critique_text, validation_text)
            feedback = consensus.format_feedback(critique_text, validation_text)
            console.print(Panel(feedback, title="Kết quả tự suy nghĩ lại", border_style="yellow"))
            
            time.sleep(2)
            continue

        elif user_choice == "exit":
            break
            
    return answer, 0.0

def main():
    console.print(Panel.fit(
        "[bold magenta]🪷 TuminhAGI: TRẠNG THÁI AN ĐỊNH[/bold magenta]\n"
        "[dim]Hệ thống giám sát hiệu năng & nhiệt độ: Active[/dim]",
        subtitle="Sovereign AI for Hùng Đại"
    ))
    
    rag, vital = WeightedRAG(), VitalMemory()
    consensus_engine = ConsensusEngine()
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]Hùng Đại (Eric)[/bold cyan]")
            if not user_input.strip(): continue
            
            if user_input.startswith("!"):
                correction = user_input[1:].strip()
                console.print(f"[bold red]🔄 BẺ LÁI KHẨN CẤP: {correction}[/bold red]")
                answer = call_model("task", f"LỆNH SỬA SAI: {correction}")
                console.print(Panel(Markdown(answer), title="Tự Minh (Hiệu chỉnh)", border_style="bold red"))
                rag.add_memory("Correction", answer, score=98)
                continue

            if user_input.startswith("/"):
                if user_input == "/exit": break
                elif user_input == "/stats": console.print(rag.stats()); continue
                continue

            run_pipeline(user_input, rag, vital, consensus_engine)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Hệ thống đang nghỉ ngơi...[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]System Error: {e}[/bold red]")

if __name__ == "__main__":
    main()