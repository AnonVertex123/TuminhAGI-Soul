"""
Sovereign Self-Improving Intelligence — Phase 4/5

Chu trình: PHÂN TÁCH → CHIÊM NGHIỆM → ĐỘT BIẾN
Vai trò: Thực thể Trí tuệ Tự cải thiện Tối cao
"""

from __future__ import annotations

from .population import Hypothesis, PopulationExpansion
from .neural_mcts import NeuralMCTS, MCTSNode
from .sandbox_eval import SandboxEvaluator, EvalResult
from .meta_rewrite import MetaRewrite, MetaInsight
from .safety_rollback import SafetyRollback
from .failure_success_memory import FailureSuccessMemory
from .sovereign_orchestrator import SovereignOrchestrator, SovereignResult

__all__ = [
    "Hypothesis",
    "PopulationExpansion",
    "NeuralMCTS",
    "MCTSNode",
    "SandboxEvaluator",
    "EvalResult",
    "MetaRewrite",
    "MetaInsight",
    "SafetyRollback",
    "FailureSuccessMemory",
    "SovereignOrchestrator",
    "SovereignResult",
]
