import os
import time
import ollama
from pathlib import Path
from functools import wraps
from rich.console import Console
from config import PROMPTS_DIR, MODEL_TASK, MODEL_CRITIC, MODEL_VALIDATOR

console = Console()

class LLMClient:
    def __init__(self):
        self.models = {
            "task": MODEL_TASK,
            "data": MODEL_TASK,
            "critic": MODEL_CRITIC,
            "validator": MODEL_VALIDATOR
        }
        self.last_call_time = 0
        self.cooldown = 1.5 # Giây nghỉ để bảo vệ GPU

    def _get_system_prompt(self, persona: str) -> str:
        prompt_file = PROMPTS_DIR / f"{persona}_agent.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return f"Bạn là {persona} agent của TuminhAGI."

    def call(self, persona: str, message: str, context: str = "") -> str:
        """Gọi model AI với cơ chế hạ nhiệt GPU và đo hiệu năng."""
        model = self.models.get(persona, MODEL_TASK)
        system_prompt = self._get_system_prompt(persona)
        
        # Đảm bảo khoảng nghỉ 'Thiền' cho GPU
        elapsed = time.perf_counter() - self.last_call_time
        if elapsed < self.cooldown:
            time.sleep(self.cooldown - elapsed)
        
        messages = [
            {"role": "system", "content": f"{system_prompt}\n\n[CONTEXT]\n{context}\n[/CONTEXT]"},
            {"role": "user", "content": message}
        ]
        
        start_time = time.perf_counter()
        try:
            response = ollama.chat(model=model, messages=messages)
            content = response["message"]["content"]
            
            duration = time.perf_counter() - start_time
            console.print(f"[bold magenta]⚡ [Tự Minh]: {persona} agent phản hồi trong {duration:.2f}s[/bold magenta]")
            
            self.last_call_time = time.perf_counter()
            return content
        except Exception as e:
            console.print(f"[bold red]❌ Lỗi gọi model {model}: {e}[/bold red]")
            return ""

    async def call_async(self, persona: str, message: str, context: str = ""):
        # Placeholder cho tương lai khi dùng ollama-python async
        pass
