"""
Neo Cá nhân — Tuminh_Brain.jsonl (personal knowledge gate)

Mục tiêu:
- Trích các "nếp nhăn" liên quan từ memory/TUMINH_BRAIN.jsonl theo keyword.
- Chèn vào context/prompt để agent ưu tiên triết lý & sở thích của riêng huynh.
- KHÔNG thay thế các lớp neo khác (Wikipedia/Official docs); chỉ bổ sung "cái gu" và pattern đã học.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _normalize(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


@dataclass
class BrainHit:
    entry: dict[str, Any]
    score: int


def _load_brain_jsonl(brain_file: Path) -> list[dict[str, Any]]:
    if not brain_file.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(brain_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _tokenize_query(user_message: str, *, min_len: int = 3, max_tokens: int = 25) -> list[str]:
    """
    Tokenization nhẹ (không phụ thuộc NLP libs).
    """
    txt = user_message or ""
    # giữ chữ có dấu bằng cách dùng class Unicode đơn giản (regex không hoàn hảo nhưng đủ)
    tokens = re.findall(r"[A-Za-zÀ-ỹ0-9_]+", txt)
    norm_tokens: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        t2 = _normalize(t)
        if len(t2) < min_len:
            continue
        if t2 in seen:
            continue
        seen.add(t2)
        norm_tokens.append(t2)
        if len(norm_tokens) >= max_tokens:
            break
    return norm_tokens


def build_neo_personal_context(user_message: str, *, brain_file: Path | None = None, top_k: int = 3) -> str:
    """
    Trả về block text để inject vào context.
    """
    if brain_file is None:
        brain_file = Path("I:/TuminhAgi/memory/TUMINH_BRAIN.jsonl")

    entries = _load_brain_jsonl(brain_file)
    if not entries:
        return ""

    tokens = _tokenize_query(user_message)
    if not tokens:
        return ""

    hits: list[BrainHit] = []
    # Scoring cực nhẹ: token xuất hiện trong json blob => cộng điểm
    for e in entries:
        blob = json.dumps(e, ensure_ascii=False).casefold()
        score = 0
        for t in tokens:
            if t in blob:
                score += 1
        if score > 0:
            hits.append(BrainHit(entry=e, score=score))

    if not hits:
        return ""

    hits.sort(key=lambda h: (h.score, -len(h.entry.get("logic_pattern", ""))), reverse=True)
    selected = [h.entry for h in hits[:top_k]]

    lines: list[str] = []
    lines.append("[NEO CÁ NHÂN — TUMINH_BRAIN.jsonl]")
    for i, e in enumerate(selected, 1):
        cat = e.get("category", "")
        pat = e.get("logic_pattern", "")
        lesson = e.get("lesson", "")
        core = e.get("core_syntax", "")
        lines.append(f"{i}. [{cat}] {pat}")
        if core:
            lines.append(f"   SYNTAX: {core}")
        if lesson:
            # Không nhồi quá dài
            short_lesson = str(lesson).strip()
            if len(short_lesson) > 500:
                short_lesson = short_lesson[:499] + "…"
            lines.append(f"   LESSON: {short_lesson}")

    lines.append("[/NEO CÁ NHÂN — TUMINH_BRAIN.jsonl]")
    return "\n".join(lines)


__all__ = ["build_neo_personal_context"]

