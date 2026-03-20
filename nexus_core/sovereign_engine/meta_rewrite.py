"""
TỰ CHUYỂN HÓA CẤU TRÚC (Meta-Self-Rewrite)

KHÔNG CHỈ SỬA CODE — Phân tích tại sao tư duy cũ dẫn đến giải pháp kém.
Cập nhật Thinking_Engine, Failure-Success Memory 4-tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .sandbox_eval import EvalResult

TIER_CRITICAL_FAILURE = 1
TIER_MEDIUM_FAILURE = 2
TIER_SUCCESS = 3
TIER_BREAKTHROUGH = 4


@dataclass
class MetaInsight:
    root_cause: str
    recommended_change: str
    tier: int


class MetaRewrite:
    """
    Phân tích root cause, cập nhật Thinking_Engine, Failure-Success Memory.
    """

    def __init__(
        self,
        memory_path: Path | None = None,
        call_llm: Callable[[str, str], str] | None = None,
    ):
        self._memory_path = memory_path or Path(__file__).parent.parent.parent / "memory" / "sovereign_failure_success.json"
        self._call_llm = call_llm

    def analyze_failure(self, result: EvalResult) -> MetaInsight | None:
        """
        Phân tích tại sao solution thua cuộc.
        """
        if result.survived:
            return None
        if not self._call_llm:
            return MetaInsight(
                root_cause="Low score in Correctness/Complexity/Elegance",
                recommended_change="Review scoring criteria",
                tier=TIER_MEDIUM_FAILURE,
            )
        try:
            prompt = (
                f"Solution thua (correctness={result.correctness}, complexity={result.complexity_score}, "
                f"elegance={result.elegance}). Phân tích root cause NGẮN GỌN (1-2 câu) và đề xuất thay đổi."
            )
            out = self._call_llm("Bạn là analyst.", prompt)
            return MetaInsight(
                root_cause=out[:200] if out else "Unknown",
                recommended_change="Integrate insight into MCTS ranking",
                tier=TIER_MEDIUM_FAILURE if result.total < 0.3 else TIER_CRITICAL_FAILURE,
            )
        except Exception:
            return None

    def record_outcome(self, insight: MetaInsight, tier: int) -> None:
        """
        Ghi vào Failure-Success Memory (4-tier).
        """
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        # Stub: append to file hoặc JSON
        data = {"tier": tier, "root_cause": insight.root_cause, "recommended_change": insight.recommended_change}
        with open(self._memory_path, "a", encoding="utf-8") as f:
            f.write(str(data) + "\n")
