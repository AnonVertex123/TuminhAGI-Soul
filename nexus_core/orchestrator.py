import re
import subprocess
import time
import ollama
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown

from config import (
    SOUL_VAULT_DIR, MODEL_TASK, MODEL_CRITIC, MODEL_VALIDATOR, 
    MAX_RETRY, MIN_CONFIDENCE, CONTEXT_TOP_K, SOUL_CONSTANTS
)
from nexus_core.weighted_rag import WeightedRAG
from nexus_core.vital_memory import VitalMemory
from nexus_core.consensus import ConsensusEngine
from nexus_core.self_improve import SelfImprove
from nexus_core.eternal_memory import EternalMemoryManager
from nexus_core.mission_manager import MissionManager
from nexus_core.first_aid_dna import SpinalReflexEngine

console = Console()

class TuminhOrchestrator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TuminhOrchestrator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self.rag = WeightedRAG()
        self.vital = VitalMemory()
        self.consensus = ConsensusEngine()
        self.self_improve = SelfImprove()
        self.eternal = EternalMemoryManager()
        self.mission_runner = MissionManager()
        self.spinal_reflex = SpinalReflexEngine()
        self.last_snapshot_time = time.time()
        self._initialized = True

    def get_available_models(self):
        """Fetches list of available models from local Ollama."""
        try:
            response = ollama.list()
            return [m.model for m in response.models]
        except Exception:
            return []

    def validate_model_fallback(self, model_name: str, available_models: list[str]) -> str:
        """Returns the model if available, otherwise falls back to MODEL_TASK."""
        if model_name in available_models or f"{model_name}:latest" in available_models:
            return model_name
        console.print(f"[yellow]⚠️ Warning: Model {model_name} not found. Falling back to {MODEL_TASK}[/yellow]")
        return MODEL_TASK

    def call_model(self, persona: str, message: str, context: str = "") -> str:
        prompt_file = SOUL_VAULT_DIR / f"{persona}_agent.txt"
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        else:
            system_prompt = f"Bạn là {persona} agent."
            
        # Inject SOUL Constants into every call to ensure alignment
        soul_text = "\n\n[SOUL CONSTANTS - IMPERATIVE]\n"
        for key, val in SOUL_CONSTANTS.items():
            soul_text += f"- {key.upper()}: {val}\n"
        system_prompt += soul_text
        
        available = self.get_available_models()
        if persona in ["task", "data", "med_gen", "philo", "finance", "logic_math"]:
            model = self.validate_model_fallback(MODEL_TASK, available)
        elif persona == "critic":
            model = self.validate_model_fallback(MODEL_CRITIC, available)
        elif persona in ["validator", "router"]:
            model = self.validate_model_fallback(MODEL_VALIDATOR, available)
        else:
            model = self.validate_model_fallback(MODEL_TASK, available)
            
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

    def detect_domain(self, question: str) -> tuple[str, float]:
        """Uses LLM to detect the domain of the question to route to the correct expert agent."""
        router_resp = self.call_model("router", f"PHÂN LOẠI CÂU HỎI: {question}")
        parsed = self.consensus.parse_json(router_resp, "router")
        
        domain = parsed.get("domain", "task").lower()
        try:
            confidence = float(parsed.get("confidence", 0.5))
        except (ValueError, TypeError):
            confidence = 0.5
            
        return domain, confidence

    def extract_and_run_code(self, text: str) -> str:
        """Extracts and executes code blocks preceded by 'EXECUTE: type'."""
        sql_blocks = re.findall(r"EXECUTE: SQL\s+```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        py_blocks = re.findall(r"EXECUTE: PYTHON\s+```python\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        viz_blocks = re.findall(r"EXECUTE: VIZ\s+```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        
        results = []
        
        # 1. Handle SQL
        for sql in sql_blocks:
            console.print(f"[bold blue]🔎 Running SQL Query via Data Engine...[/bold blue]")
            res = self.mission_runner.execute_mission("data_engine", args=["--sql", sql])
            results.append(f"[SQL RESULT]\n{res.get('output', res.get('message'))}\n[/SQL RESULT]")
            
        # 2. Handle Python
        for py in py_blocks:
            console.print(f"[bold blue]🐍 Running Python Code via Data Engine...[/bold blue]")
            # Ensure path separation if needed, but subprocess handles it
            res = self.mission_runner.execute_mission("data_engine", args=["--code", py])
            results.append(f"[PYTHON RESULT]\n{res.get('output', res.get('message'))}\n[/PYTHON RESULT]")
            
        # 3. Handle Visualization
        for viz in viz_blocks:
            console.print(f"[bold blue]📊 Generating Chart via Viz Tool...[/bold blue]")
            res = self.mission_runner.execute_mission("viz_tool", args=["--json", viz])
            results.append(f"[VIZ RESULT]\n{res.get('output', res.get('message'))}\n[/VIZ RESULT]")
            
        return "\n".join(results)

    def check_mission_snapshot(self):
        """Saves a snapshot of active missions every 5 minutes."""
        if time.time() - self.last_snapshot_time >= 300:
            try:
                missions = self.mission_runner.registry
                snapshot_data = f"[MISSION SNAPSHOT] Available missions: {list(missions.keys())}"
                self.eternal.add_memory(snapshot_data, is_vital=True, human_score=100)
                self.last_snapshot_time = time.time()
                console.print("[dim][cyan]💾 Mission Hub snapshot saved to Eternal DB.[/cyan][/dim]")
            except Exception as e:
                console.print(f"[dim][yellow]⚠️ Snapshot failed: {e}[/yellow][/dim]")

    def run_pipeline(self, question: str, phase: int) -> tuple[str, float]:
        # Step -2: Spinal Reflex Intercept (sub-10ms bypass)
        reflex_action = self.spinal_reflex.intercept_prompt(question)
        if reflex_action:
            console.print("[bold red]⚡ [SPINAL REFLEX] Emergency condition matched! Executing immediate response...[/bold red]")
            return reflex_action, 1.0

        # Step 0: Vital Shortcut & Snapshots
        self.check_mission_snapshot()
        try:
            vital_hits = self.eternal.retrieve_memory(question, k=1)
            if vital_hits and vital_hits[0]['score'] >= 80:
                console.print(f"[bold green]✨ [VITAL SHORTCUT] Found high-certainty memory (Score: {vital_hits[0]['score']})[/bold green]")
                return vital_hits[0]['content'], vital_hits[0]['score'] / 100.0
        except Exception: pass

        # 1. Mission Control & Context
        mission_output, full_context = self._get_pipeline_context(question)
        
        # 3. Domain Routing
        domain, route_conf = self.detect_domain(question)
        if route_conf < 0.8:
            domain = Prompt.ask(f"Accept domain {domain.upper()}?", default=domain)

        answer = ""
        confidence = 0.0

        for attempt in range(MAX_RETRY):
            console.print(f"\n[bold yellow]Attempt {attempt + 1}/{MAX_RETRY}[/bold yellow]")
            
            # 4. Expert Call & Self-Correction (v1.5)
            answer = self._get_refined_answer(domain, question, full_context)

            # 5. Execution Layer
            execution_res = self.extract_and_run_code(answer) if domain == "data" else ""
            if execution_res:
                console.print(Panel(execution_res, title="[MISSION CONTROL] Results"))

            # 6. Final Consensus
            critique_text = self.call_model("critic", f"Q: {question}\nA: {answer}\nData: {execution_res}")
            val_msg = f"Q: {question}\nA: {answer}\nCritic: {critique_text}"
            validation_text = self.call_model("validator", val_msg, full_context + execution_res)
            
            is_approved, confidence = self.consensus.check(critique_text, validation_text)
            console.print(Panel(self.consensus.format_feedback(critique_text, validation_text), 
                                title="Consensus", border_style="green" if is_approved else "red"))

            if is_approved:
                self._finalize_success(question, answer, execution_res, confidence)
                return answer, confidence

            if attempt == MAX_RETRY - 1:
                console.print("[bold red]❌ PIPELINE FAILED CONSENSUS. MANUAL INTERVENTION REQUIRED.[/bold red]")
                return answer, 0.0

            if self.consensus.should_ask_human(attempt, MAX_RETRY, confidence, MIN_CONFIDENCE):
                break
                
        return answer, confidence

    def _get_pipeline_context(self, question: str):
        mission_output = ""
        matched = self.mission_runner.match_mission(question)
        if matched:
            result = self.mission_runner.execute_mission(matched)
            mission_output = f"\n[MISSION RESULT: {matched}]\n{result.get('output')}\n[/MISSION RESULT]"
        
        retrieved = self.rag.retrieve(question, top_k=CONTEXT_TOP_K)
        eternal_mems = self.eternal.retrieve_memory(question, k=3)
        eternal_context = "\n[ETERNAL AWARENESS]\n" + "\n".join([f"- {m['content']} (Score: {m['score']})" for m in eternal_mems]) + "\n[/ETERNAL AWARENESS]"
        full_context = self.vital.format_context(retrieved) + eternal_context + mission_output
        return mission_output, full_context

    def _get_refined_answer(self, domain, question, full_context):
        import json
        answer = self.call_model(domain, f"Câu hỏi: {question}", full_context)
        for i in range(2): # Self-Correction Loop
            critique_resp = self.call_model("critic", f"Review: {answer}")
            crit_data = self.consensus.parse_json(critique_resp, "critic")
            if float(crit_data.get("score", 0)) >= 7:
                break
            console.print(f"[yellow]⚠️ Critic Score {crit_data.get('score')}/10. Refinement {i+1}/2...[/yellow]")
            answer = self.call_model(domain, f"Lỗi cần sửa: {json.dumps(crit_data.get('issues'))}\nGợi ý: {json.dumps(crit_data.get('suggestions'))}", f"Previous: {answer}")
        return answer

    def _finalize_success(self, question, answer, execution, confidence):
        try:
            score = int(confidence * 100)
            self.rag.add_memory(question, answer, score=score)
            self.eternal.add_memory(f"Q: {question}\nA: {answer}\nExec: {execution}", human_score=score)
        except Exception as e:
            console.print(f"[dim]Auto-save failed: {e}[/dim]")

def main():
    console.print(Panel.fit("[bold magenta]🪷 TuminhAGI Orchestrator[/bold magenta]\n[dim]Initializing nexus core (Eternal Awareness Enabled)...[/dim]"))
    
    orchestrator = TuminhOrchestrator()
    
    stats = orchestrator.rag.stats()
    phase = orchestrator.self_improve.check_phase(stats.get("vital", 0))
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
                console.print(orchestrator.rag.stats())
                continue
            elif cmd == "/prune":
                removed = orchestrator.rag.prune(dry_run=False)
                console.print(f"Pruned {removed} weak memories.")
                continue
            elif cmd == "/memories":
                for m in orchestrator.rag.memories[-5:]:
                    console.print(f"[{m['tier'].upper()}] {m['id']} (Score: {m['score']})")
                continue
            elif cmd.startswith("/reinforce "):
                try:
                    mem_id = cmd.split(" ")[1]
                    orchestrator.rag.reinforce(mem_id)
                    console.print(f"Reinforced memory {mem_id}")
                except IndexError:
                    console.print("Usage: /reinforce <mem_id>")
                continue
                
            answer, conf = orchestrator.run_pipeline(user_input, phase)
            
            if conf < MIN_CONFIDENCE:
                fb = Prompt.ask("[bold red]Provide feedback/correction to improve[/bold red]")
                if fb:
                    orchestrator.eternal.add_memory(f"Correction for '{user_input}': {fb}", is_vital=True)
                    orchestrator.rag.add_memory(user_input, f"Correction: {fb}", score=80)
                    console.print("[green]Feedback incorporated as VITAL memory.[/green]")
                    
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]System Error: {e}[/bold red]")

if __name__ == "__main__":
    main()
