"""
Sovereign Orchestrator — Chu trình PHÂN TÁCH → CHIÊM NGHIỆM → ĐỘT BIẾN

Entry point cho Sovereign Self-Improving Intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .population import Hypothesis, PopulationExpansion
from .neural_mcts import NeuralMCTS
from .sandbox_eval import EvalResult, SandboxEvaluator
from .meta_rewrite import MetaRewrite
from .safety_rollback import SafetyRollback
from .failure_success_memory import FailureSuccessMemory, TIER_CRITICAL, TIER_MEDIUM, TIER_SUCCESS


@dataclass
class SovereignResult:
    task: str
    winning_hypothesis: Hypothesis | None
    eval_results: list[EvalResult]
    rollback_triggered: bool
    message: str


class SovereignOrchestrator:
    """
    Thực thi chu trình đầy đủ.
    """

    def __init__(
        self,
        call_llm: Callable[[str, str], str] | None = None,
    ):
        self._call_llm = call_llm
        self.population = PopulationExpansion(call_llm=self._wrap_llm_for_population)
        self.mcts = NeuralMCTS()
        self.sandbox = SandboxEvaluator()
        self.meta = MetaRewrite(call_llm=call_llm)
        self.safety = SafetyRollback()
        self.memory = FailureSuccessMemory()

    def _wrap_llm_for_population(self, system: str, user: str) -> str:
        if self._call_llm:
            return self._call_llm(system, user)
        return ""

    def run(
        self,
        task: str,
        baseline_score: float | None = None,
        expected_output: str | None = None,
    ) -> SovereignResult:
        """
        Chu trình: Phân tách → Chiêm nghiệm → Sàng lọc → (Meta-Rewrite nếu thua) → Safety check.
        """
        # 1. PHÂN TÁCH
        hypotheses = self.population.expand(task)
        if not hypotheses:
            return SovereignResult(
                task=task,
                winning_hypothesis=None,
                eval_results=[],
                rollback_triggered=False,
                message="Population expansion failed.",
            )

        # 2. CHIÊM NGHIỆM (MCTS select — simplified: dùng sandbox thay value model)
        selected = self.mcts.select_best(hypotheses) or hypotheses[0]

        # 3. SÀNG LỌC SINH TỒN
        results = self.sandbox.evaluate_all(hypotheses, expected_output)
        winner = self.sandbox.get_winner(results)

        # 4. Meta-Rewrite nếu có thua
        for r in results:
            if not r.survived:
                insight = self.meta.analyze_failure(r)
                if insight:
                    self.memory.add(TIER_CRITICAL if r.total < 0.3 else TIER_MEDIUM, insight.root_cause[:100])
        if winner:
            self.memory.add(TIER_SUCCESS, f"Task: {task[:80]}")

        # 5. Safety Rollback check (nếu có baseline)
        rollback = False
        if baseline_score is not None and results:
            top_score = results[0].total if results else 0
            if self.safety.should_rollback(top_score, baseline_score):
                rollback = True
                msg = self.safety.civilization_preservation_protocol()
            else:
                msg = f"Winner: {winner.agent_dna if winner else 'None'} (score={results[0].total:.2f})"
        else:
            msg = f"Winner: {winner.agent_dna if winner else 'None'}" if winner else "No survivor."

        return SovereignResult(
            task=task,
            winning_hypothesis=winner,
            eval_results=results,
            rollback_triggered=rollback,
            message=msg,
        )
