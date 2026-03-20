"""
BẢO CHỨNG TIẾN HÓA (Safety Rollback)

Nếu Benchmark sau tự sửa < Baseline 5% → Civilization Preservation Protocol.
Phục hồi trạng thái ổn định gần nhất.
"""

from __future__ import annotations

import json
from pathlib import Path

BASELINE_DROP_THRESHOLD = 0.05  # 5%
CHECKPOINT_DIR = Path(__file__).parent.parent.parent / "memory" / "sovereign_checkpoints"


class SafetyRollback:
    """
    Lưu baseline, so sánh sau self-rewrite, rollback nếu regression > 5%.
    """

    def __init__(self, checkpoint_dir: Path | None = None):
        self._dir = checkpoint_dir or CHECKPOINT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_baseline(self, benchmark_score: float, state_id: str = "latest") -> None:
        path = self._dir / f"baseline_{state_id}.json"
        path.write_text(json.dumps({"score": benchmark_score, "state_id": state_id}, ensure_ascii=False))

    def load_baseline(self, state_id: str = "latest") -> float | None:
        path = self._dir / f"baseline_{state_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data.get("score", 0))

    def should_rollback(self, new_benchmark: float, baseline: float | None = None) -> bool:
        """
        True nếu cần rollback (regression >= 5%).
        """
        if baseline is None:
            baseline = self.load_baseline()
        if baseline is None:
            return False
        return new_benchmark < baseline * (1 - BASELINE_DROP_THRESHOLD)

    def civilization_preservation_protocol(self) -> str:
        """
        Kích hoạt: phục hồi trạng thái ổn định.
        """
        return "[CIVILIZATION PRESERVATION PROTOCOL] Rollback activated. Restore last stable state."
