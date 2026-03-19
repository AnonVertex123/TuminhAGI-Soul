"""
agents/shadow_learner.py — TuminhAGI Shadow Learner
====================================================
Chay ngam, theo doi moi thay doi .py/.tsx/.ts trong du an.
Moi khi Cursor luu file (Ctrl+S):
  1. Lay git diff cua file do
  2. Gui diff cho phi4-mini de phan tich
  3. Neu phi4-mini tim thay "nep nhan" moi -> ghi vao memory/brain_gate.json
  4. brain_watcher.py se tu dong nap vao TUMINH_BRAIN.jsonl

Cach chay:
  python agents/shadow_learner.py              # watch toan bo du an
  python agents/shadow_learner.py --path src/  # watch thu muc cu the
  python agents/shadow_learner.py --dry-run    # xem diff nhung khong nap
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    print("[ERROR] Thieu watchdog. Chay: pip install watchdog")
    sys.exit(1)

# ── Config ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
GATE_FILE    = PROJECT_ROOT / "memory" / "brain_gate.json"
BRAIN_FILE   = PROJECT_ROOT / "memory" / "TUMINH_BRAIN.jsonl"
IGNORE_DIRS  = {".git", ".venv", "Lib", "__pycache__", ".next", "node_modules", "memory", "agents"}
WATCH_EXTS   = {".py", ".tsx", ".ts"}
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi4-mini"
DEBOUNCE_S   = 2.5   # giay im lang truoc khi xu ly (tranh spam khi Cursor auto-save)
MAX_DIFF_CHARS = 3000  # cat diff qua dai de tranh token overflow

# ── Utilities ────────────────────────────────────────────────────────────────

def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _git_diff(file_path: str) -> str:
    """Lay staged + unstaged diff cua mot file."""
    try:
        # staged diff
        staged = subprocess.check_output(
            ["git", "diff", "--cached", file_path],
            cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL, text=True, encoding="utf-8"
        )
        # unstaged diff
        unstaged = subprocess.check_output(
            ["git", "diff", file_path],
            cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL, text=True, encoding="utf-8"
        )
        combined = (staged + unstaged).strip()
        return combined[:MAX_DIFF_CHARS] if combined else ""
    except Exception:
        return ""


def _call_phi4(diff: str, file_name: str) -> dict[str, Any] | None:
    """
    Gui diff cho phi4-mini, yeu cau tra ve JSON voi cau truc Brain.
    Tra ve None neu Ollama khong chay hoac khong tim duoc pattern dang ke.
    """
    import urllib.request

    prompt = f"""You are TuminhAGI Shadow Learner. Analyze this Git diff from file "{file_name}".

TASK: Extract ONE reusable software engineering or medical-AI knowledge pattern from this change.
If the diff is trivial (whitespace, comment typo, variable rename), respond with: {{"skip": true}}

Otherwise respond with ONLY valid JSON (no markdown, no explanation):
{{
  "category": "<Optimization|Safety|Caching|Architecture|Medical Logic|NumPy/Math|NLP/Embedding|Testing>",
  "logic_pattern": "<short name, max 8 words>",
  "core_syntax": "<most reusable 1-3 lines of code from the diff>",
  "lesson": "<root cause: WHY this approach wins, 1 sentence, include Big-O or causal reason>",
  "tags": ["tag1", "tag2"]
}}

GIT DIFF:
{diff}

JSON RESPONSE:"""

    body = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }).encode()

    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read())["response"].strip()

        # Strip markdown fences if model added them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        if parsed.get("skip"):
            return None
        return parsed
    except Exception as e:
        print(f"  [WARN] phi4-mini error: {e}")
        return None


def _load_brain_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if not BRAIN_FILE.exists():
        return keys
    with open(BRAIN_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                keys.add((e.get("category", ""), e.get("logic_pattern", "")))
            except Exception:
                pass
    return keys


def _write_gate(entry: dict[str, Any]) -> None:
    """
    Ghi entry vao gate file.
    Neu gate da ton tai (watcher chua kip doc), append thanh array.
    """
    GATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if GATE_FILE.exists():
        try:
            existing = json.loads(GATE_FILE.read_text(encoding="utf-8-sig"))
            if isinstance(existing, list):
                existing.append(entry)
            else:
                existing = [existing, entry]
            GATE_FILE.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return
        except Exception:
            pass  # gate bi corrupt -> overwrite

    GATE_FILE.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Watcher ──────────────────────────────────────────────────────────────────

class ShadowLearner(FileSystemEventHandler):
    def __init__(self, dry_run: bool = False) -> None:
        super().__init__()
        self.dry_run = dry_run
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_modified(self, event: Any) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix not in WATCH_EXTS:
            return
        # Kiem tra ignore dirs
        if any(d in path.parts for d in IGNORE_DIRS):
            return

        # Debounce: reset timer moi khi co event moi cho cung file
        rel = str(path.relative_to(PROJECT_ROOT) if path.is_absolute() else path)
        with self._lock:
            if rel in self._timers:
                self._timers[rel].cancel()
            t = threading.Timer(DEBOUNCE_S, self._process, args=(str(path), rel))
            self._timers[rel] = t
            t.start()

    def _process(self, abs_path: str, rel_path: str) -> None:
        with self._lock:
            self._timers.pop(rel_path, None)

        print(f"\n[SHADOW] Phat hien thay doi: {rel_path}")

        diff = _git_diff(abs_path)
        if not diff:
            print(f"  [SKIP] Khong co git diff (file chua duoc track hoac khong co thay doi)")
            return

        print(f"  [DIFF] {len(diff)} chars — dang gui cho phi4-mini phan tich...")

        if self.dry_run:
            print("  [DRY-RUN] Se khong nap vao brain. Diff preview:")
            print("  " + diff[:400].replace("\n", "\n  "))
            return

        entry = _call_phi4(diff, Path(rel_path).name)
        if entry is None:
            print(f"  [SKIP] Diff qua don gian hoac Ollama khong chay")
            return

        # Kiem tra trung lap voi brain hien tai
        brain_keys = _load_brain_keys()
        key = (entry.get("category", ""), entry.get("logic_pattern", ""))
        if key in brain_keys:
            print(f"  [SKIP] Da ton tai trong brain: [{key[0]}] {key[1]}")
            return

        # Inject metadata
        entry["timestamp"] = _stamp()
        entry["source"] = f"Shadow Learner / {rel_path}"

        _write_gate(entry)
        print(f"  [OK] Gate ghi: [{entry['category']}] -- {entry['logic_pattern']}")
        print(f"  [OK] brain_watcher.py se nap vao TUMINH_BRAIN sau <1 giay")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="TuminhAGI Shadow Learner")
    parser.add_argument("--path",    default=".", help="Thu muc can theo doi")
    parser.add_argument("--dry-run", action="store_true", help="Hien diff nhung khong nap brain")
    parser.add_argument("--fast",    action="store_true", help="Debounce 0.5s thay vi 2.5s")
    args = parser.parse_args()

    global DEBOUNCE_S
    if args.fast:
        DEBOUNCE_S = 0.5

    watch_path = str(PROJECT_ROOT / args.path) if args.path != "." else str(PROJECT_ROOT)

    handler = ShadowLearner(dry_run=args.dry_run)
    observer = Observer()
    observer.schedule(handler, watch_path, recursive=True)
    observer.start()

    mode = "[DRY-RUN] " if args.dry_run else ""
    print(f"[SHADOW] {mode}TuminhAGI Shadow Learner -- ON")
    print(f"[SHADOW] Dang quan sat: {watch_path}")
    print(f"[SHADOW] Debounce: {DEBOUNCE_S}s | Model: {OLLAMA_MODEL}")
    print(f"[SHADOW] Ctrl+C de dung.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    print("\n[SHADOW] Da dung. Brain duoc bao ve.")


if __name__ == "__main__":
    main()
