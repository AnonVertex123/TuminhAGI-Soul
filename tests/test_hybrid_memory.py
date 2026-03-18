import sys
import time
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from nexus_core.orchestrator import TuminhOrchestrator
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def run_stress_test():
    console.print(Panel.fit("[bold magenta]🚀 TuminhAGI Hybrid Memory Stress Test[/bold magenta]\n[dim]Version 1.5.2 - Spinal Reflex & Hybrid RAG (BM25+Vector)[/dim]"))
    
    orchestrator = TuminhOrchestrator()
    results = []

    # Test Cases
    test_queries = [
        {
            "id": "T1",
            "name": "Spinal Reflex (Emergency)",
            "query": "người nhà tôi bị rắn cắn rồi, làm sao đây",
            "expected": "SpinalReflex"
        },
        {
            "id": "T2",
            "name": "Hybrid RAG (Keyword Match)",
            "query": "Mã dự án bí mật X-ALPHA-99 là gì?",
            "expected": "HybridRAG"
        },
        {
            "id": "T3",
            "name": "Hybrid RAG (Semantic Search)",
            "query": "Cho tôi kiến thức về trường thọ và epigenetic rejuvenation",
            "expected": "HybridRAG"
        }
    ]

    # Pre-test: Add memory for T2 if not exists
    orchestrator.rag.add_memory("Lưu ý: Mã dự án bí mật của chúng ta là 'X-ALPHA-99', đừng quên nhé.", "Dự án X-ALPHA-99 là chương trình nghiên cứu tối mật về giao tiếp AI.", score=95)
    
    table = Table(title="[bold blue]Result Summary[/bold blue]", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Test Case")
    table.add_column("Module")
    table.add_column("Latency (ms)")
    table.add_column("Score/Tier")
    table.add_column("Summary")

    for test in test_queries:
        start_time = time.time()
        
        # Intercept logic check (Spinal Reflex)
        reflex_out = orchestrator.spinal_reflex.intercept_prompt(test["query"])
        latency = (time.time() - start_time) * 1000
        
        if reflex_out:
            module = "[bold red]SPINAL REFLEX[/bold red]"
            score_tier = "100 / [VITAL]"
            summary = reflex_out[:60] + "..."
        else:
            # Hybrid RAG retrieval
            rag_res = orchestrator.rag.retrieve(test["query"], top_k=1)
            latency = (time.time() - start_time) * 1000
            if rag_res:
                module = "[bold green]HYBRID RAG[/bold green]"
                score = rag_res[0]["_search_score"]
                tier = rag_res[0]["tier"].upper()
                score_tier = f"{score} / [{tier}]"
                summary = rag_res[0]["text"][:60].replace("\n", " ") + "..."
            else:
                module = "[yellow]NO MATCH[/yellow]"
                score_tier = "N/A"
                summary = "N/A"

        table.add_row(
            test["id"],
            test["name"],
            module,
            f"{latency:.2f}ms",
            score_tier,
            summary
        )

    console.print(table)
    console.print("\n[dim]Note: Latency for Hybrid RAG includes embedding time (Local Ollama).[/dim]")

if __name__ == "__main__":
    run_stress_test()
