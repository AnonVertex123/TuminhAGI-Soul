#!/usr/bin/env python3
"""
Chạy Data Collector — Bơm máu cho tiến hóa.

Usage:
  python scripts/run_data_collector.py [--iterations 3] [--domain Python]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

try:
    from nexus_core.llm_client import LLMClient
except ImportError:
    LLMClient = None


def main():
    parser = argparse.ArgumentParser(description="Data Collector — Tự tạo task, tự giải, tự chấm")
    parser.add_argument("--iterations", type=int, default=2, help="Số thế hệ")
    parser.add_argument("--domain", type=str, default="Python", help="Python | Algorithm | Architecture")
    parser.add_argument("--quiet", action="store_true", help="Ít log")
    args = parser.parse_args()

    call_llm = None
    if LLMClient:
        client = LLMClient()
        call_llm = lambda sys_p, msg: client.call("task", msg, sys_p)

    from nexus_core.training.data_collector import DataCollector

    collector = DataCollector(call_llm=call_llm)
    stats = collector.run_experience_loop(
        iterations=args.iterations,
        domain=args.domain,
        baseline_score=0.7,
        verbose=not args.quiet,
    )

    summary = collector.finalize_training_data()
    print("\n--- Xuất training data ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    return 0 if stats["value_samples"] > 0 or stats["dpo_pairs"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
