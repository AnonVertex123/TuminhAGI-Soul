"""
SÀNG LỌC SINH TỒN (Survival of the Fittest)

Sandbox evaluation: 40% Correctness, 30% O(n) Complexity, 30% Elegance.
Thua → Cái Chết. Thắng → Mã nguồn gốc cho thế hệ sau.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .population import Hypothesis

WEIGHT_CORRECTNESS = 0.4
WEIGHT_COMPLEXITY = 0.3
WEIGHT_ELEGANCE = 0.3


@dataclass
class EvalResult:
    hypothesis: Hypothesis
    correctness: float
    complexity_score: float  # cao = tốt (O(n) tốt hơn O(n²))
    elegance: float
    total: float
    survived: bool


class SandboxEvaluator:
    """
    Chấm điểm theo trọng số. Survival of the fittest.
    """

    SURVIVAL_THRESHOLD = 0.5  # Dưới ngưỡng → Cái Chết

    def __init__(self, run_in_sandbox: bool = True):
        self._run_in_sandbox = run_in_sandbox

    def evaluate(self, hypothesis: Hypothesis, expected_output: str | None = None) -> EvalResult:
        """
        Chấm: Correctness (40%), Complexity (30%), Elegance (30%).
        """
        correct = self._score_correctness(hypothesis, expected_output)
        complexity = self._score_complexity(hypothesis)
        elegance = self._score_elegance(hypothesis)
        total = correct * WEIGHT_CORRECTNESS + complexity * WEIGHT_COMPLEXITY + elegance * WEIGHT_ELEGANCE
        survived = total >= self.SURVIVAL_THRESHOLD
        return EvalResult(hypothesis, correct, complexity, elegance, total, survived)

    def evaluate_all(
        self, hypotheses: list[Hypothesis], expected_output: str | None = None
    ) -> list[EvalResult]:
        results = [self.evaluate(h, expected_output) for h in hypotheses]
        return sorted(results, key=lambda r: r.total, reverse=True)

    def get_winner(self, results: list[EvalResult]) -> Hypothesis | None:
        survivors = [r for r in results if r.survived]
        return survivors[0].hypothesis if survivors else None

    def _score_correctness(self, h: Hypothesis, expected: str | None) -> float:
        if not h.solution:
            return 0.0
        if expected and expected in h.solution:
            return 1.0
        return 0.7  # heuristic: có solution = partial credit

    def _score_complexity(self, h: Hypothesis) -> float:
        code = h.solution
        if not code:
            return 0.5
        # Heuristic: phạt O(n²) patterns
        bad = len(re.findall(r"for\s+.*for\s+", code)) + len(re.findall(r"\.append\s*\(.*for", code))
        return max(0.2, 1.0 - bad * 0.3)

    def _score_elegance(self, h: Hypothesis) -> float:
        code = h.solution
        if not code:
            return 0.5
        lines = [l for l in code.split("\n") if l.strip()]
        # Ngắn gọn nhưng có nội dung
        if 5 <= len(lines) <= 50:
            return 0.8
        if len(lines) < 5:
            return 0.6
        return 0.5  # quá dài = kém elegant
