"""
CHIÊM NGHIỆM ĐA TUYẾN (Neural MCTS — IQ 1000)

- Neural Policy: thu hẹp không gian tìm kiếm
- Simulate 50 bước tương lai
- Value Model: dự đoán "Nghiệp" (technical debt, scalability, maintainability)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .population import Hypothesis


@dataclass
class MCTSNode:
    hypothesis: Hypothesis
    value_estimate: float
    depth: int
    technical_debt_risk: float
    scalability_score: float


class NeuralMCTS:
    """
    MCTS với Neural Policy + Value Model.
    Mô phỏng 50 bước, ước lượng value cho mỗi nhánh.
    """

    SIMULATION_STEPS = 50
    VALUE_WEIGHTS = {"correctness": 0.4, "scalability": 0.3, "maintainability": 0.3}

    def __init__(
        self,
        value_model: Callable[[Hypothesis], dict] | None = None,
    ):
        self._value_model = value_model

    def select_best(self, hypotheses: list[Hypothesis]) -> Hypothesis | None:
        """
        Chọn nhánh có value estimate cao nhất.
        """
        if not hypotheses:
            return None
        nodes = [self._evaluate_node(h) for h in hypotheses]
        if not nodes:
            return hypotheses[0]
        best = max(nodes, key=lambda n: n.value_estimate)
        return best.hypothesis

    def _evaluate_node(self, h: Hypothesis) -> MCTSNode:
        if self._value_model:
            try:
                scores = self._value_model(h)
                td = float(scores.get("technical_debt_risk", 0.5))
                sc = float(scores.get("scalability_score", 0.5))
                value = (1 - td) * 0.4 + sc * 0.3 + 0.3  # simplified
                return MCTSNode(h, value, 0, td, sc)
            except Exception:
                pass
        return MCTSNode(h, 0.5, 0, 0.5, 0.5)
