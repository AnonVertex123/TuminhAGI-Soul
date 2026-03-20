"""
Neo Chuyên môn (Y văn) — GS. Đỗ Tất Lợi

Mục tiêu:
- Khi câu hỏi liên quan đến thuốc/ vị thuốc / herb name / liều / chống chỉ định,
  truy xuất từ data/tuminh_herb_encyclopedia.jsonl (nguồn GS. Đỗ Tất Lợi).
- Chèn vào context để agent trả lời dựa trên dữ liệu chính quy (anti-hallucination).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _normalize(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


@dataclass
class HerbHit:
    herb: dict[str, Any]
    score: int


@lru_cache(maxsize=1)
def _load_herb_index(herb_file: str) -> list[dict[str, Any]]:
    p = Path(herb_file)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _is_medical_query(user_message: str) -> bool:
    low = (user_message or "").lower()
    markers = ["thuốc", "vị thuốc", "thảo dược", "liều", "liều lượng", "chống chỉ định", "contraindications", "uống", "sắc", "hãm", "bài thuốc", "đau", "bệnh"]
    return any(m in low for m in markers)


def _score_herb(user_message_norm: str, herb: dict[str, Any]) -> int:
    score = 0
    vn = _normalize(str(herb.get("name_vn", "")))
    latin = _normalize(str(herb.get("name_latin", "")))
    hid = _normalize(str(herb.get("herb_id", "")))
    if vn and vn in user_message_norm:
        score += 5
    if latin and latin in user_message_norm:
        score += 3
    if hid and hid in user_message_norm:
        score += 2

    # Token match fallback (để bắt khi người dùng chỉ nói một phần)
    # Chỉ lấy token độ dài vừa phải để giảm false-positive.
    if score == 0 and vn:
        vn_tokens = [t for t in vn.split(" ") if len(t) >= 3]
        for t in vn_tokens[:4]:
            if t in user_message_norm:
                score += 1
    return score


def build_neo_gs_do_tat_loi_context(user_message: str, *, herb_file: str = "I:/TuminhAgi/data/tuminh_herb_encyclopedia.jsonl", top_k: int = 4) -> str:
    if not user_message or len(user_message.strip()) < 3:
        return ""
    if not _is_medical_query(user_message):
        # vẫn cho phép nếu user nhắc thẳng tên vị thuốc (heuristic theo herb_id/tên)
        pass

    herbs = _load_herb_index(herb_file)
    if not herbs:
        return ""

    qn = _normalize(user_message)
    hits: list[HerbHit] = []
    for h in herbs:
        sc = _score_herb(qn, h)
        if sc > 0:
            hits.append(HerbHit(herb=h, score=sc))

    if not hits:
        return ""

    hits.sort(key=lambda x: (x.score, len(str(x.herb.get("conditions_vn", "")))), reverse=True)
    selected = [h.herb for h in hits[:top_k]]

    # Format dữ liệu gọn để đưa vào prompt
    lines: list[str] = []
    lines.append("[NEO CHUYÊN MÔN — GS. Đỗ Tất Lợi (Y văn chính quy)]")
    for i, h in enumerate(selected, 1):
        name_vn = h.get("name_vn", "")
        nhom = h.get("nhom", "")
        tinh = h.get("tinh", "")
        evidence = h.get("evidence_level", "")
        safety = h.get("safety_level", "")
        usage = h.get("usage", "")
        dosage = h.get("dosage", "")
        contraindications = h.get("contraindications", [])
        if isinstance(contraindications, list):
            contraindications_txt = "; ".join([str(x) for x in contraindications[:5]])
        else:
            contraindications_txt = str(contraindications)
        lines.append(f"{i}. {name_vn} — Nhóm: {nhom} | Tinh: {tinh} | An toàn: {safety} | Bằng chứng: {evidence}")
        if usage:
            lines.append(f"   Usage: {usage}")
        if dosage:
            lines.append(f"   Dosage: {dosage}")
        if contraindications_txt:
            lines.append(f"   Chống chỉ định: {contraindications_txt}")

    lines.append("[/NEO CHUYÊN MÔN — GS. Đỗ Tất Lợi (Y văn chính quy)]")
    return "\n".join(lines)


__all__ = ["build_neo_gs_do_tat_loi_context"]

