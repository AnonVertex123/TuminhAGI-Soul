import time
import ollama
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from config import (
    PROMPTS_DIR, MODEL_TASK, MODEL_CRITIC, MODEL_VALIDATOR, 
    MAX_RETRY, MIN_CONFIDENCE, CONTEXT_TOP_K
)
from nexus_core.weighted_rag import WeightedRAG
from nexus_core.vital_memory import VitalMemory
from nexus_core.consensus import ConsensusEngine
from nexus_core.self_improve import SelfImprove

console = Console()

def call_model(persona: str, message: str, context: str = "") -> str:
    prompt_file = PROMPTS_DIR / f"{persona}_agent.txt"
    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    else:
        system_prompt = f"Bạn là {persona} agent."
        
    if persona in ["task", "data"]:
        model = MODEL_TASK
    elif persona == "critic":
        model = MODEL_CRITIC
    elif persona == "validator":
        model = MODEL_VALIDATOR
    else:
        model = MODEL_TASK
        
    full_prompt = system_prompt
    if context:
        full_prompt += f"\n\n[CONTEXT]\n{context}\n[/CONTEXT]"
        
    messages = [
        {"role": "system", "content": full_prompt},
        {"role": "user", "content": message}
    ]
    
    try:
        response = ollama.chat(model=model, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        console.print(f"[red]Error calling model {model}: {e}[/red]")
        return ""

def detect_agent(question: str) -> str:
    keywords = ["data", "csv", "sql", "bảng", "thống kê", "phân tích", "biểu đồ", "excel", "dataframe"]
    q_lower = question.lower()
    if any(kw in q_lower for kw in keywords):
        return "data"
    return "task"

def run_pipeline(question: str, rag: WeightedRAG, vital: VitalMemory, consensus: ConsensusEngine, phase: int) -> tuple[str, float]:
    retrieved = rag.retrieve(question, top_k=CONTEXT_TOP_K)
    context = vital.format_context(retrieved)
    agent_type = detect_agent(question)
    
    console.print(f"[blue]=> Routing to {agent_type.upper()} Agent[/blue]")
    
    answer = ""
    confidence = 0.0
    
    for attempt in range(MAX_RETRY):
        console.print(f"\n[bold yellow]Attempt {attempt + 1}/{MAX_RETRY}[/bold yellow]")
        
        answer = call_model(agent_type, f"Câu hỏi: {question}", context)
        console.print(Panel(Markdown(answer), title=f"{agent_type.capitalize()} Output"))
        
        critique_msg = f"Câu hỏi gốc: {question}\nCâu trả lời cần review:\n{answer}"
        critique_text = call_model("critic", critique_msg)
        console.print(f"[dim]Critic response generated...[/dim]")
        
        val_msg = f"Câu hỏi gốc: {question}\nCâu trả lời: {answer}\nNhận xét từ Critic:\n{critique_text}"
        validation_text = call_model("validator", val_msg, context)
        console.print(f"[dim]Validator response generated...[/dim]")
        
        is_approved, confidence = consensus.check(critique_text, validation_text)
        
        feedback_summary = consensus.format_feedback(critique_text, validation_text)
        console.print(Panel(feedback_summary, title="Consensus Check", border_style="green" if is_approved else "red"))
        
        if is_approved:
            rag.add_memory(question, answer, score=int(confidence * 100))
            return answer, confidence
            
        if consensus.should_ask_human(attempt, MAX_RETRY, confidence, MIN_CONFIDENCE):
            break
            
    console.print("[bold red]! Pipeline failed to reach consensus. Need human intervention.[/bold red]")
    return answer, confidence

def main():
    console.print(Panel.fit("[bold magenta]🪷 TuminhAGI Orchestrator[/bold magenta]\n[dim]Initializing nexus core...[/dim]"))
    
    rag = WeightedRAG()
    vital = VitalMemory()
    consensus_engine = ConsensusEngine()
    self_improve = SelfImprove()
    
    stats = rag.stats()
    phase = self_improve.check_phase(stats.get("vital", 0))
    console.print(f"[green]System Ready. Current Phase: {phase} | Total Memories: {stats['total']}[/green]")
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            if not user_input.strip():
                continue
                
            cmd = user_input.strip().lower()
            if cmd == "/exit":
                console.print("Goodbye!")
                break
            elif cmd == "/stats":
                console.print(rag.stats())
                continue
            elif cmd == "/prune":
                removed = rag.prune(dry_run=False)
                console.print(f"Pruned {removed} weak memories.")
                continue
            elif cmd == "/memories":
                for m in rag.memories[-5:]:
                    console.print(f"[{m['tier'].upper()}] {m['id']} (Score: {m['score']})")
                continue
            elif cmd.startswith("/reinforce "):
                try:
                    mem_id = cmd.split(" ")[1]
                    rag.reinforce(mem_id)
                    console.print(f"Reinforced memory {mem_id}")
                except IndexError:
                    console.print("Usage: /reinforce <mem_id>")
                continue
                
            answer, conf = run_pipeline(user_input, rag, vital, consensus_engine, phase)
            
            if conf < MIN_CONFIDENCE:
                fb = Prompt.ask("[bold red]Provide feedback/correction to improve[/bold red]")
                if fb:
                    rag.add_memory(user_input, f"Correction: {fb}", score=80)
                    console.print("[green]Feedback incorporated as vital memory.[/green]")
                    
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]System Error: {e}[/bold red]")

if __name__ == "__main__":
    main()
