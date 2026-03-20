"""
Failure-Success Memory — Cơ chế nén 4-tier

Tier 1: Critical failure (never repeat)
Tier 2: Medium failure (penalty)
Tier 3: Success pattern (boost)
Tier 4: Breakthrough (amplify)
"""

from __future__ import annotations

import json
from pathlib import Path

TIER_CRITICAL = 1
TIER_MEDIUM = 2
TIER_SUCCESS = 3
TIER_BREAKTHROUGH = 4


class FailureSuccessMemory:
    """
    4-tier memory: critical_failures, medium_failures, successes, breakthroughs.
    """

    def __init__(self, path: Path | None = None):
        self._path = path or Path(__file__).parent.parent.parent / "memory" / "sovereign_fs_memory.json"

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "tier1_critical": [],
            "tier2_medium": [],
            "tier3_success": [],
            "tier4_breakthrough": [],
        }

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, tier: int, entry: str, max_per_tier: int = 100) -> None:
        data = self._load()
        key = {
            TIER_CRITICAL: "tier1_critical",
            TIER_MEDIUM: "tier2_medium",
            TIER_SUCCESS: "tier3_success",
            TIER_BREAKTHROUGH: "tier4_breakthrough",
        }.get(tier, "tier2_medium")
        lst = data.setdefault(key, [])
        if entry not in lst:
            lst.append(entry)
            data[key] = lst[-max_per_tier:]
        self._save(data)

    def get_critical_failures(self) -> list[str]:
        return self._load().get("tier1_critical", [])

    def should_avoid(self, pattern: str) -> bool:
        """Check nếu pattern nằm trong critical failures."""
        critical = self.get_critical_failures()
        return any(p in pattern for p in critical)
