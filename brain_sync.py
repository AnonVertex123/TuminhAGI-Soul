"""
brain_sync.py — TuminhAGI Knowledge Ingestion System
=====================================================
Mỗi khi Cursor vừa code xong một đoạn "khét", chạy file này để nạp tri thức.

Cách dùng:
  python brain_sync.py                        # Interactive mode
  python brain_sync.py --query "Rút tủy"      # Tự động query brain hiện tại
  python brain_sync.py --stats                # Thống kê não bộ
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import io
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows terminals
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BRAIN_FILE = Path(__file__).parent / "memory" / "TUMINH_BRAIN.jsonl"
CATEGORIES = [
    "Optimization",
    "Safety",
    "Architecture",
    "Caching",
    "NLP/Embedding",
    "Medical Logic",
    "NumPy/Math",
    "API/Backend",
    "Frontend/UI",
    "Testing",
]


# ── Core I/O ────────────────────────────────────────────────────────────────

def append_to_brain(
    category: str,
    pattern: str,
    syntax: str,
    lesson: str,
    source: str = "Cursor Session",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Nạp một 'Nếp nhăn' mới vào TUMINH_BRAIN.jsonl."""
    BRAIN_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry: dict[str, Any] = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "category": category,
        "logic_pattern": pattern,
        "core_syntax": syntax,
        "lesson": lesson,
        "source": source,
        "tags": tags or [],
    }

    with open(BRAIN_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n[OK] Da nap 1 nep nhan moi vao TUMINH_BRAIN: [{category}] -- {pattern}")
    return entry


def load_brain() -> list[dict[str, Any]]:
    """Đọc toàn bộ brain."""
    if not BRAIN_FILE.exists():
        return []
    entries = []
    with open(BRAIN_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


# ── Stats & Query ────────────────────────────────────────────────────────────

def print_stats() -> None:
    entries = load_brain()
    if not entries:
        print("Não bộ chưa có dữ liệu.")
        return

    from collections import Counter
    cats = Counter(e.get("category", "?") for e in entries)
    print(f"\n{'═'*55}")
    print(f"  TUMINH_BRAIN — {len(entries)} nếp nhăn  |  {len(cats)} danh mục")
    print(f"{'═'*55}")
    for cat, count in cats.most_common():
        bar = "█" * count
        print(f"  {cat:<20s} {bar} ({count})")
    print(f"{'─'*55}")
    print(f"  Cập nhật lần cuối: {entries[-1]['timestamp']}")
    print(f"{'═'*55}\n")


def query_brain(keyword: str) -> None:
    entries = load_brain()
    keyword_lower = keyword.lower()
    results = [
        e for e in entries
        if keyword_lower in json.dumps(e, ensure_ascii=False).lower()
    ]
    if not results:
        print(f"Khong tim thay ket qua cho: '{keyword}'")
        return
    print(f"\nTìm thấy {len(results)} nếp nhăn khớp với '{keyword}':\n")
    for i, e in enumerate(results, 1):
        print(f"[{i}] {e['timestamp']} | {e['category']} | {e['logic_pattern']}")
        print(f"     Lesson: {e['lesson']}")
        print(f"     Syntax: {e['core_syntax'][:80]}{'...' if len(e['core_syntax']) > 80 else ''}\n")


# ── Interactive Mode ─────────────────────────────────────────────────────────

def interactive_mode() -> None:
    print(f"\n{'═'*55}")
    print("  RUT TUY TRI THUC — TuminhAGI Brain Sync")
    print(f"{'═'*55}")

    print("\nDanh muc co san:")
    for i, c in enumerate(CATEGORIES, 1):
        print(f"  {i:2d}. {c}")

    raw_cat = input("\nPhân loại (số hoặc tên tự do): ").strip()
    if raw_cat.isdigit() and 1 <= int(raw_cat) <= len(CATEGORIES):
        category = CATEGORIES[int(raw_cat) - 1]
    else:
        category = raw_cat or "General"

    pattern = input("Mẫu hình / Pattern (vd: Red Flag Protocol): ").strip()
    syntax  = input("Cú pháp sát thủ / Killer Syntax: ").strip()
    lesson  = input("Bài học cốt lõi / Deep Lesson: ").strip()
    source  = input("Nguồn gốc (Enter = Cursor Session): ").strip() or "Cursor Session"
    raw_tags = input("Tags (cách nhau bằng dấu phẩy, có thể bỏ trống): ").strip()
    tags    = [t.strip() for t in raw_tags.split(",") if t.strip()]

    append_to_brain(category, pattern, syntax, lesson, source, tags)


# ── Batch Seed (nạp hàng loạt) ──────────────────────────────────────────────

def seed_initial_brain() -> None:
    """Nạp toàn bộ tri thức từ phiên làm việc 2026-03-19 vào brain."""
    knowledge: list[dict[str, Any]] = [

        # ── NumPy / Math ────────────────────────────────────────────────
        {
            "category": "NumPy/Math",
            "logic_pattern": "Numerically Stable Softmax",
            "core_syntax": "arr=(arr-arr.max())/temp; e=np.exp(arr); return (e/e.sum()).tolist()",
            "lesson": "Trừ max() trước np.exp() ngăn overflow; numpy SIMD nhanh 50x vòng lặp Python",
            "tags": ["softmax", "overflow", "simd"],
        },
        {
            "category": "NumPy/Math",
            "logic_pattern": "O(N) Top-K với argpartition",
            "core_syntax": "part=np.argpartition(arr,-k)[-k:]; return part[np.argsort(arr[part])[::-1]]",
            "lesson": "argpartition=O(N) vs argsort=O(N log N); tại N=70k cho kết quả 12x nhanh hơn",
            "tags": ["top-k", "argpartition", "complexity"],
        },
        {
            "category": "NumPy/Math",
            "logic_pattern": "Matrix Cosine Similarity (unit_vault)",
            "core_syntax": "unit_vault=emb/norm(emb,axis=1,keepdims=True); scores=unit_q @ unit_vault.T",
            "lesson": "Pre-normalize 1 lần lúc load; dot(unit_a,unit_b)=cosine(a,b); BLAS làm phần nặng",
            "tags": ["cosine", "embedding", "blas", "precompute"],
        },
        {
            "category": "NumPy/Math",
            "logic_pattern": "Bayesian Update Vectorized",
            "core_syntax": "posterior=priors*likelihoods; return posterior/posterior.sum()",
            "lesson": "Cập nhật xác suất N bệnh sau 1 câu hỏi Có/Không trong 1 phép nhân vector",
            "tags": ["bayesian", "probability", "vectorized"],
        },

        # ── Safety / Medical Logic ───────────────────────────────────────
        {
            "category": "Safety",
            "logic_pattern": "Adaptive Threshold (Red Flag Protocol)",
            "core_syntax": "threshold = 0.25 if any(kw in text for kw in _RED_FLAGS) else 0.38",
            "lesson": "Cost asymmetry: bỏ sót bệnh nguy hiểm >> báo nhầm; threshold tỷ lệ nghịch mức nguy hiểm",
            "tags": ["threshold", "safety", "medical", "red-flag"],
        },
        {
            "category": "Safety",
            "logic_pattern": "Emergency Bypass Before All Filters",
            "core_syntax": "if _is_emergency_case(query): return allow_with_warning(result)",
            "lesson": "Kiểm tra class nguy hiểm TRƯỚC mọi filter; reject bệnh cấp cứu = lỗi nghiêm trọng nhất",
            "tags": ["emergency", "bypass", "priority"],
        },
        {
            "category": "Medical Logic",
            "logic_pattern": "Synonym Expansion cho ICD Vector Matching",
            "core_syntax": "prompt: 'Standard Term (synonym1, synonym2)' -> embed toàn bộ string",
            "lesson": "Embedding drift khi dịch máy; inject synonyms kéo rộng vector coverage về phía ICD codes",
            "tags": ["synonym", "embedding", "icd", "nlp"],
        },
        {
            "category": "Medical Logic",
            "logic_pattern": "Pathognomonic Boost (dấu hiệu đặc trưng)",
            "core_syntax": "if fever_kw & neck_kw: probs['A39'] = max(probs['A39'], 0.85)",
            "lesson": "Cặp triệu chứng 'vàng' (sốt cao+cứng cổ) tự động đẩy xác suất Meningitis >85%",
            "tags": ["pathognomonic", "boost", "meningitis", "clinical"],
        },

        # ── Caching ──────────────────────────────────────────────────────
        {
            "category": "Caching",
            "logic_pattern": "LRU Cache cho Hot Path Phase-1",
            "core_syntax": "@lru_cache(maxsize=2048)\ndef suggest_p1(symptoms_lower: str) -> list: ...",
            "lesson": "Phase-1 questions (keyword-based) không cần LLM; cache hit=0.15us vs LLM=2-5s",
            "tags": ["lru_cache", "latency", "phase1"],
        },
        {
            "category": "Caching",
            "logic_pattern": "Sentinel Pattern (None vs MISS)",
            "core_syntax": "_MISS=object(); v=cache.get(k,_MISS); if v is not _MISS: return v",
            "lesson": "cache.get(k) trả None cho cả 'không có' lẫn 'đã lưu None'; sentinel giải quyết ambiguity",
            "tags": ["sentinel", "cache", "none-handling"],
        },
        {
            "category": "Caching",
            "logic_pattern": "frozenset cho O(1) keyword lookup",
            "core_syntax": "_KW: frozenset = frozenset(['sốt cao', 'chest pain', ...])",
            "lesson": "frozenset hash tại compile-time; any(kw in text for kw in frozenset) = O(1) mỗi kw",
            "tags": ["frozenset", "o1", "hot-path"],
        },

        # ── Architecture / Backend ───────────────────────────────────────
        {
            "category": "Architecture",
            "logic_pattern": "SSE Streaming với Queue + Worker Thread",
            "core_syntax": "q=Queue(); threading.Thread(target=worker,args=(q,)).start(); yield from q_generator(q)",
            "lesson": "FastAPI async event_gen đọc từ queue; worker thread chạy sync Python logic; no blocking",
            "tags": ["sse", "streaming", "queue", "fastapi"],
        },
        {
            "category": "Architecture",
            "logic_pattern": "Phase-1 Early Emit (Time-to-First-Question < 1ms)",
            "core_syntax": "q.put('__DIFF_QUESTIONS__'+json.dumps(p1_qs)); # trước mọi Ollama call",
            "lesson": "Tách phase-1 (keyword) ra khỏi phase-2 (LLM); bác sĩ thấy câu hỏi gợi ý ngay lập tức",
            "tags": ["latency", "ux", "phase1", "early-emit"],
        },
        {
            "category": "Architecture",
            "logic_pattern": "Professor Reasoning Engine (sub-2ms)",
            "core_syntax": "insight = ProfessorReasoning.analyze(symptoms, cands, probs) # pure numpy",
            "lesson": "Red flags + pathognomonic boost + differential exclusion = 0.039ms; decoupled từ LLM",
            "tags": ["professor", "reasoning", "latency", "numpy"],
        },

        # ── Optimization ─────────────────────────────────────────────────
        {
            "category": "Optimization",
            "logic_pattern": "HardMapping → Cache → LLM (Priority Ladder)",
            "core_syntax": "hard=hard_map(text); if hard: return hard  # trước khi gọi LLM",
            "lesson": "LLM chỉ là fallback cuối; hard map = 0ms, LRU cache = 0.07us, LLM = 2-30s",
            "tags": ["latency", "priority", "hardmap", "fallback"],
        },
        {
            "category": "Optimization",
            "logic_pattern": "Warm-up tại Server Startup",
            "core_syntax": "@app.on_event('startup')\nasync def warmup(): threading.Thread(target=_load).start()",
            "lesson": "Pre-load ICD vault + pre-seed LRU cache khi khởi động; request đầu tiên không bị cold start",
            "tags": ["warmup", "cold-start", "startup"],
        },
    ]

    existing = load_brain()
    existing_keys = {(e.get("category"), e.get("logic_pattern")) for e in existing}

    added = 0
    for kn in knowledge:
        key = (kn["category"], kn["logic_pattern"])
        if key in existing_keys:
            continue  # Không nạp trùng
        append_to_brain(
            kn["category"],
            kn["logic_pattern"],
            kn["core_syntax"],
            kn["lesson"],
            source="Cursor Session 2026-03-19 / Tự Minh V9.1",
            tags=kn.get("tags", []),
        )
        added += 1

    print(f"\n[DONE] +{added} nep nhan moi | Tong cong: {len(existing) + added} nep nhan")


# ── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="TuminhAGI Brain Sync")
    parser.add_argument("--stats",  action="store_true", help="Thống kê não bộ")
    parser.add_argument("--query",  type=str, default="", help="Tìm kiếm trong brain")
    parser.add_argument("--seed",   action="store_true", help="Nạp tri thức ban đầu từ V9.1")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    elif args.query:
        query_brain(args.query)
    elif args.seed:
        seed_initial_brain()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
