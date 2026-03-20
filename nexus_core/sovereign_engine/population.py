"""
PHÂN TÁCH (Population Expansion)

3 Agent ảo: Optimizer, Architect, Visionary — mỗi đưa ra Hypothesis độc lập.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

DNA_OPTIMIZER = "OPT"   # Tối ưu tốc độ
DNA_ARCHITECT = "ARC"   # Cấu trúc bền vững
DNA_VISIONARY = "VIS"   # Giải pháp đột phá


@dataclass
class Hypothesis:
    agent_dna: str
    task: str
    solution: str
    reasoning: str = ""


class PopulationExpansion:
    """
    Khởi tạo 3 Agent với 3 DNA, mỗi Agent tạo 1 Hypothesis.
    """

    DNA_PROMPTS = {
        DNA_OPTIMIZER: (
            "Bạn là Agent OPTIMIZER — tối ưu tốc độ, giảm latency, cache. "
            "Đưa ra giải pháp NHANH NHẤT có thể."
        ),
        DNA_ARCHITECT: (
            "Bạn là Agent ARCHITECT — cấu trúc bền vững, modular, dễ mở rộng. "
            "Đưa ra giải pháp CÓ THỂ BẢO TRÌ lâu dài."
        ),
        DNA_VISIONARY: (
            "Bạn là Agent VISIONARY — giải pháp đột phá, out-of-box. "
            "Đưa ra giải pháp SÁNG TẠO nhất."
        ),
    }

    def __init__(self, call_llm: Callable[[str, str], str] | None = None):
        self._call_llm = call_llm

    def expand(self, task: str) -> list[Hypothesis]:
        """
        Tạo 3 Hypothesis từ 3 Agent.
        """
        hypotheses: list[Hypothesis] = []
        for dna, prompt in self.DNA_PROMPTS.items():
            h = self._generate_hypothesis(task, dna, prompt)
            if h:
                hypotheses.append(h)
        return hypotheses

    def _generate_hypothesis(self, task: str, dna: str, system_prompt: str) -> Hypothesis | None:
        if not self._call_llm:
            return Hypothesis(agent_dna=dna, task=task, solution="", reasoning="[stub]")
        try:
            out = self._call_llm(system_prompt, f"Task: {task}\n\nĐưa ra giải pháp (code hoặc mô tả):")
            return Hypothesis(agent_dna=dna, task=task, solution=out or "", reasoning="")
        except Exception:
            return None
