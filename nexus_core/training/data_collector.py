"""
DATA COLLECTOR — Bơm "máu" cho tiến hóa

Module chạy ngầm: tự tạo bài tập, tự giải, tự chấm điểm, đóng gói thành bộ Dataset chuẩn.
- raw_experience.jsonl: Code + Score → train Value Model ("Mắt thần")
- dpo_pairs.jsonl: (Tốt/Xấu) → train DPO ("Phân biệt thiện ác")
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

# Ensure project root in path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nexus_core.sovereign_engine.sovereign_orchestrator import SovereignOrchestrator, SovereignResult
from nexus_core.sovereign_engine.failure_success_memory import FailureSuccessMemory


# Templates bài toán "sát thủ" — test giới hạn model
SYNTHETIC_TASK_TEMPLATES = {
    "Python": [
        "Optimize a Python function to find prime numbers using Sieve of Eratosthenes.",
        "Implement a thread-safe Singleton pattern in Python.",
        "Write a Python script to compress data using Huffman coding.",
        "Implement binary search with O(log n) — handle edge cases: empty list, single element.",
        "Write a decorator that memoizes function results with LRU eviction (max 100 entries).",
        "Implement a Python generator for Fibonacci sequence without storing full list.",
    ],
    "Algorithm": [
        "Implement Top-K with O(N) using quickselect/argpartition.",
        "Implement merge sort in-place with O(1) extra space.",
        "Detect cycle in linked list with O(1) space (Floyd).",
    ],
    "Architecture": [
        "Design a rate limiter (sliding window) with O(1) per request.",
        "Implement a simple event bus with publish/subscribe.",
    ],
}

DPO_MIN_GAP = 0.2  # Chỉ lưu DPO pair nếu chênh lệch score >= 0.2


class DataCollector:
    """
    Tự tạo task → Sovereign Orchestrator giải → Lưu Value + DPO dataset.
    """

    def __init__(
        self,
        orchestrator: SovereignOrchestrator | None = None,
        memory: FailureSuccessMemory | None = None,
        call_llm: Callable[[str, str], str] | None = None,
        data_dir: Path | str | None = None,
    ):
        self.orch = orchestrator or SovereignOrchestrator(call_llm=call_llm)
        self.memory = memory or self.orch.memory
        self._data_dir = Path(data_dir) if data_dir else _ROOT / "data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dataset_path = self._data_dir / "raw_experience.jsonl"
        self.dpo_dataset_path = self._data_dir / "dpo_pairs.jsonl"

    def generate_synthetic_tasks(
        self,
        domain: str = "Python",
        max_tasks: int = 6,
        call_llm: Callable[[str, str], str] | None = None,
    ) -> list[str]:
        """
        Tạo bài toán 'sát thủ' — có thể dùng LLM mạnh hoặc template.
        """
        templates = SYNTHETIC_TASK_TEMPLATES.get(domain, SYNTHETIC_TASK_TEMPLATES["Python"])
        tasks = list(templates)[:max_tasks]

        if call_llm:
            try:
                prompt = (
                    f"Tạo {max_tasks} bài toán lập trình {domain} khó, "
                    "test giới hạn: tối ưu O(n), edge cases, concurrency. Mỗi dòng 1 bài:"
                )
                out = call_llm("Bạn là người tạo đề.", prompt)
                if out:
                    lines = [l.strip() for l in out.split("\n") if len(l.strip()) > 20]
                    if lines:
                        tasks = lines[:max_tasks]
            except Exception:
                pass
        return tasks

    def run_experience_loop(
        self,
        iterations: int = 3,
        domain: str = "Python",
        baseline_score: float = 0.7,
        verbose: bool = True,
    ) -> dict:
        """
        Vòng lặp tích lũy 'Nghiệp' và 'Công đức'.
        """
        tasks = self.generate_synthetic_tasks(domain=domain)
        stats = {"value_samples": 0, "dpo_pairs": 0, "rollbacks": 0}

        for i in range(iterations):
            for task in tasks:
                if verbose:
                    print(f"--- [GEN {i+1}/{iterations}] Task: {task[:60]}... ---")

                result = self.orch.run(task, baseline_score=baseline_score, expected_output=None)

                if result.rollback_triggered:
                    stats["rollbacks"] += 1
                    if verbose:
                        print("[ROLLBACK] Civilization Preservation Protocol activated.")

                self._save_value_sample(task, result, stats)
                self._prepare_dpo_sample(task, result, stats)

        if verbose:
            print(f"\n--- KẾT THÚC: {stats['value_samples']} value samples, {stats['dpo_pairs']} DPO pairs ---")
        return stats

    def _save_value_sample(self, task: str, result: SovereignResult, stats: dict) -> None:
        """Lưu Code + Score để train Value Model ('Mắt thần')."""
        if not result.eval_results:
            return
        # Lưu cả khi không có winner — best attempt vẫn có giá trị (score thấp = negative sample)
        top_eval = result.eval_results[0]
        winner = result.winning_hypothesis or top_eval.hypothesis
        if not winner.solution:
            return
        sample = {
            "instruction": task,
            "input": "",
            "output": winner.solution,
            "score": top_eval.total,
            "metadata": {
                "agent_dna": winner.agent_dna,
                "correctness": top_eval.correctness,
                "complexity_score": top_eval.complexity_score,
                "elegance": top_eval.elegance,
            },
        }
        with open(self.raw_dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        stats["value_samples"] += 1

    def _prepare_dpo_sample(self, task: str, result: SovereignResult, stats: dict) -> None:
        """Lưu cặp (Tốt/Xấu) để train DPO — AI biết 'Phân biệt thiện ác'."""
        if len(result.eval_results) < 2:
            return

        sorted_results = result.eval_results  # Đã sort theo total desc
        chosen = sorted_results[0]
        rejected = sorted_results[-1]

        if chosen.total <= rejected.total + DPO_MIN_GAP:
            return

        dpo_pair = {
            "prompt": task,
            "chosen": chosen.hypothesis.solution,
            "rejected": rejected.hypothesis.solution,
            "chosen_score": chosen.total,
            "rejected_score": rejected.total,
        }
        with open(self.dpo_dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(dpo_pair, ensure_ascii=False) + "\n")
        stats["dpo_pairs"] += 1

    def finalize_training_data(self, output_dir: Path | str | None = None) -> dict:
        """
        Nén bộ nhớ và chuẩn bị file JSONL cuối cùng cho Trainer.
        """
        out = Path(output_dir) if output_dir else self._data_dir
        out.mkdir(parents=True, exist_ok=True)

        insights_path = out / "failure_success_insights.jsonl"
        critical = self.memory.get_critical_failures()
        data = self.memory._load()

        with open(insights_path, "w", encoding="utf-8") as f:
            for tier_key, entries in data.items():
                lst = entries if isinstance(entries, list) else []
                for entry in lst[:20]:  # Top 20 mỗi tier
                    if isinstance(entry, str):
                        f.write(json.dumps({"tier": tier_key, "entry": entry}, ensure_ascii=False) + "\n")

        return {
            "raw_experience": str(self.raw_dataset_path),
            "dpo_pairs": str(self.dpo_dataset_path),
            "failure_insights": str(insights_path),
            "critical_count": len(critical),
        }
