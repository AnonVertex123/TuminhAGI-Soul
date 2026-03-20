from __future__ import annotations

import os
import shutil
from pathlib import Path


"""
Optional helper (not required by the provided workflow).

If you later want to push dataset to a HuggingFace repo, you can extend this script.
For now, it copies `data/filtered/dataset_alpaca.json` into a target folder for publishing.
"""


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    target_repo = os.environ.get("HF_REPO", "").strip()

    src = Path("data/filtered/dataset_alpaca.json")
    if not src.exists():
        raise SystemExit(f"Missing {src}")

    # No-op placeholder: keep local copy unless future extension is configured.
    if not token or not target_repo:
        print("[push_dataset] HF_TOKEN/HF_REPO not provided. No-op.")
        return

    # Placeholder: real implementation omitted intentionally.
    # This keeps the repo buildable without HuggingFace dependency.
    out_dir = Path("data/filtered/publish")
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, out_dir / src.name)
    print(f"[push_dataset] Copied dataset to {out_dir} (extend for HF publish).")


if __name__ == "__main__":
    main()

