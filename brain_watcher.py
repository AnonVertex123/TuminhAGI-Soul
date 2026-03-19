"""
brain_watcher.py — TuminhAGI Knowledge Gate Watcher
====================================================
Chạy ngầm, quét memory/brain_gate.json mỗi giây.
Hễ Cursor ghi tri thức mới vào gate -> tự nạp vào BRAIN -> xóa gate.

Cach chay:
  python brain_watcher.py              # polling mode (default, 1s interval)
  python brain_watcher.py --fast       # 0.2s interval (debug)
  python brain_watcher.py --once       # xu ly gate 1 lan roi thoat
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import io
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

GATE_FILE  = Path("memory/brain_gate.json")
BRAIN_FILE = Path("memory/TUMINH_BRAIN.jsonl")
LOCK_FILE  = Path("memory/brain_gate.lock")   # chống race condition khi Cursor ghi chưa xong

REQUIRED_FIELDS = {"category", "logic_pattern", "core_syntax", "lesson"}


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _validate(data: dict) -> tuple[bool, str]:
    """Kiểm tra cấu trúc JSON trước khi nạp."""
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        return False, f"Thieu truong: {missing}"
    for f in REQUIRED_FIELDS:
        if not str(data.get(f, "")).strip():
            return False, f"Truong '{f}' rong"
    return True, "OK"


def _load_existing_keys() -> set[tuple[str, str]]:
    """Đọc các (category, logic_pattern) đã tồn tại để tránh nạp trùng."""
    keys: set[tuple[str, str]] = set()
    if not BRAIN_FILE.exists():
        return keys
    with open(BRAIN_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    e = json.loads(line)
                    keys.add((e.get("category", ""), e.get("logic_pattern", "")))
                except json.JSONDecodeError:
                    pass
    return keys


def process_gate(verbose: bool = True) -> bool:
    """
    Xử lý brain_gate.json nếu tồn tại.
    Trả về True nếu đã nạp thành công.
    """
    if not GATE_FILE.exists():
        return False

    # Chờ lock giải phóng (Cursor đang ghi dở)
    waited = 0
    while LOCK_FILE.exists() and waited < 3.0:
        time.sleep(0.05)
        waited += 0.05

    try:
        # utf-8-sig strips BOM written by PowerShell Out-File; falls back gracefully
        raw = GATE_FILE.read_text(encoding="utf-8-sig").strip()
        if not raw:
            GATE_FILE.unlink(missing_ok=True)
            return False

        data = json.loads(raw)

        # Hỗ trợ cả single object lẫn array of objects
        entries = data if isinstance(data, list) else [data]

        BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = _load_existing_keys()
        added = 0

        with open(BRAIN_FILE, "a", encoding="utf-8") as f:
            for entry in entries:
                ok, reason = _validate(entry)
                if not ok:
                    print(f"[WARN] Bo qua entry khong hop le: {reason}")
                    continue

                key = (entry.get("category", ""), entry.get("logic_pattern", ""))
                if key in existing:
                    print(f"[SKIP] Da ton tai: [{key[0]}] {key[1]}")
                    continue

                # Chuẩn hóa: inject timestamp nếu thiếu
                entry.setdefault("timestamp", _stamp())
                entry.setdefault("source", "Cursor Auto-Inject")
                entry.setdefault("tags", [])

                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                existing.add(key)
                added += 1

                if verbose:
                    print(f"[OK] [{_stamp()}] Nap [{entry['category']}] -- {entry['logic_pattern']}")

        GATE_FILE.unlink(missing_ok=True)

        if added > 0:
            print(f"[BRAIN] +{added} nep nhan moi. Gate da xoa.")
        return added > 0

    except json.JSONDecodeError as e:
        print(f"[ERROR] brain_gate.json bi loi JSON: {e}")
        GATE_FILE.rename(GATE_FILE.with_suffix(".error.json"))
        return False
    except Exception as e:
        print(f"[ERROR] Loi dong bo: {e}")
        return False


def watch(interval: float = 1.0) -> None:
    print(f"[WATCHER] TuminhAGI Brain Watcher -- ON (interval={interval}s)")
    print(f"[WATCHER] Gate  : {GATE_FILE.resolve()}")
    print(f"[WATCHER] Brain : {BRAIN_FILE.resolve()}")
    print(f"[WATCHER] Ctrl+C de dung.\n")

    try:
        while True:
            process_gate()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[WATCHER] Dung. Brain an toan.")


def main() -> None:
    parser = argparse.ArgumentParser(description="TuminhAGI Brain Gate Watcher")
    parser.add_argument("--fast",  action="store_true", help="0.2s polling interval")
    parser.add_argument("--once",  action="store_true", help="Xu ly gate 1 lan roi thoat")
    args = parser.parse_args()

    if args.once:
        result = process_gate()
        sys.exit(0 if result else 1)
    else:
        watch(interval=0.2 if args.fast else 1.0)


if __name__ == "__main__":
    main()
