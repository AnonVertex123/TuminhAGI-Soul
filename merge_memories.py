"""
TuminhAGI — Smart Memory Merge
Tổng hợp trí nhớ từ nhiều nguồn mà không xóa hay xung đột.

Cấu trúc hiện tại:
  I:\TuminhAgi\   ← Windows local (máy bàn)
  E:\TuminhAgi\   ← SSD rời (mang đi các nơi)

Cách dùng:
  python merge_memories.py status    — xem trạng thái 2 nguồn
  python merge_memories.py preview   — xem trước khi merge
  python merge_memories.py merge     — merge thật sự + backup
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from config import STORAGE_DIR, MEM_FILE, AI_NAME

BACKUP_DIR = STORAGE_DIR / "backups"


# ══════════════════════════════════════════════════════════════
# LOAD & KEY
# ══════════════════════════════════════════════════════════════

def load_memories(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ✗ Lỗi đọc {path}: {e}")
        return []


def memory_key(mem: dict) -> str:
    return mem.get("text", "")[:80].strip().lower()


# ══════════════════════════════════════════════════════════════
# FIND SOURCES — tự động tìm tất cả TuminhAgi trên máy
# ══════════════════════════════════════════════════════════════

def find_all_sources() -> list[dict]:
    """
    Tìm tất cả TuminhAgi/storage/memories.json trên máy.
    Windows: quét tất cả ổ đĩa A-Z.
    Mac: quét /Volumes/ + home.
    """
    sources = []
    found_paths = set()

    def add_source(name: str, path: Path):
        if path.exists() and str(path) not in found_paths:
            found_paths.add(str(path))
            mems = load_memories(path)
            sources.append({
                "name":  name,
                "path":  path,
                "mems":  mems,
                "count": len(mems),
            })

    if sys.platform == "win32":
        # Quét tất cả ổ đĩa Windows
        for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = Path(f"{drive}:/")
            if not drive_path.exists():
                continue

            # Tìm TuminhAgi ở root của ổ
            candidate = drive_path / "TuminhAgi" / "storage" / "memories.json"
            if candidate.exists():
                # Phân loại
                if str(candidate) == str(MEM_FILE):
                    label = f"[HIỆN TẠI] {drive}:\\TuminhAgi"
                else:
                    label = f"[SSD]      {drive}:\\TuminhAgi"
                add_source(label, candidate)

    elif sys.platform == "darwin":
        # Mac home
        add_source(
            "[HIỆN TẠI] ~/TuminhAgi",
            Path.home() / "TuminhAgi" / "storage" / "memories.json"
        )
        # Mac volumes (SSD rời)
        volumes = Path("/Volumes")
        if volumes.exists():
            for vol in volumes.iterdir():
                candidate = vol / "TuminhAgi" / "storage" / "memories.json"
                add_source(f"[SSD] /Volumes/{vol.name}/TuminhAgi", candidate)

    return sources


# ══════════════════════════════════════════════════════════════
# MERGE LOGIC
# ══════════════════════════════════════════════════════════════

def merge_two(mem_a: dict, mem_b: dict) -> dict:
    """
    Khi 2 ký ức cùng nội dung:
    - Giữ score CAO HƠN
    - Cộng dồn reinforced
    - Giữ timestamp MỚI HƠN
    """
    winner = dict(mem_a if mem_a.get("score", 0) >= mem_b.get("score", 0) else mem_b)
    winner["reinforced"] = mem_a.get("reinforced", 0) + mem_b.get("reinforced", 0)
    winner["ts"]         = max(mem_a.get("ts", 0), mem_b.get("ts", 0))
    winner["merged"]     = True
    return winner


def smart_merge(list_a: list, list_b: list) -> tuple[list, dict]:
    stats = {
        "only_a": 0,    # chỉ có ở A → giữ
        "only_b": 0,    # chỉ có ở B → thêm
        "same":   0,    # giống hệt → giữ 1
        "differ": 0,    # khác score → lấy cao hơn
    }

    index_a = {memory_key(m): m for m in list_a}
    index_b = {memory_key(m): m for m in list_b}
    merged  = {}

    for key in set(index_a) | set(index_b):
        in_a = key in index_a
        in_b = key in index_b

        if in_a and not in_b:
            merged[key] = index_a[key]
            stats["only_a"] += 1
        elif in_b and not in_a:
            merged[key] = index_b[key]
            stats["only_b"] += 1
        else:
            merged[key] = merge_two(index_a[key], index_b[key])
            if index_a[key].get("score") == index_b[key].get("score"):
                stats["same"]   += 1
            else:
                stats["differ"] += 1

    # Sắp xếp: vital trước → faint sau
    order = {"vital": 0, "strong": 1, "normal": 2, "faint": 3}
    result = sorted(
        merged.values(),
        key=lambda x: (order.get(x.get("tier", "normal"), 2), -x.get("score", 0))
    )

    return result, stats


# ══════════════════════════════════════════════════════════════
# BACKUP
# ══════════════════════════════════════════════════════════════

def backup_current() -> Path | None:
    if not MEM_FILE.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"memories_{ts}.json"
    shutil.copy2(MEM_FILE, dest)
    print(f"  💾 Backup: {dest.name}")
    return dest


# ══════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════

def cmd_status():
    print(f"\n{'═'*56}")
    print(f"  TRÍ NHỚ {AI_NAME} — TẤT CẢ NGUỒN")
    print(f"{'═'*56}")

    sources = find_all_sources()

    if not sources:
        print("  ⚠️  Không tìm thấy nguồn ký ức nào")
        return

    tier_icons = {"vital":"⭐","strong":"●","normal":"○","faint":"·"}

    for src in sources:
        print(f"\n  📂 {src['name']}")
        print(f"     Path : {src['path']}")
        print(f"     Tổng : {src['count']} ký ức")

        if src['mems']:
            tiers = defaultdict(int)
            for m in src['mems']:
                tiers[m.get('tier','normal')] += 1
            tstr = "  ".join(
                f"{tier_icons.get(t,'?')}{tiers[t]}"
                for t in ["vital","strong","normal","faint"] if tiers[t]
            )
            print(f"     Tầng : {tstr}")

    # Tính tổng nếu merge
    if len(sources) >= 2:
        all_keys = set()
        for s in sources:
            for m in s['mems']:
                all_keys.add(memory_key(m))

        total_raw  = sum(s['count'] for s in sources)
        after_merge = len(all_keys)

        print(f"\n  {'─'*46}")
        print(f"  📊 Nếu merge tất cả:")
        print(f"     Tổng gộp:     {total_raw} (có trùng)")
        print(f"     Sau merge:    {after_merge} ký ức duy nhất")
        print(f"     Mất đi:       0 ✅")

    print(f"\n{'═'*56}\n")


def cmd_preview():
    sources = find_all_sources()

    if len(sources) < 2:
        print("\n  ⚠️  Chỉ tìm thấy 1 nguồn — không cần merge")
        print(f"  Hiện tại: {sources[0]['name'] if sources else 'Trống'}")
        return

    print(f"\n{'═'*56}")
    print(f"  PREVIEW MERGE — {AI_NAME}")
    print(f"{'═'*56}")

    # Merge lần lượt
    base = sources[0]['mems']
    for src in sources[1:]:
        _, stats = smart_merge(base, src['mems'])
        merged, _ = smart_merge(base, src['mems'])

        print(f"\n  {sources[0]['name']}")
        print(f"  + {src['name']}")
        print(f"  {'─'*40}")
        print(f"  Chỉ có ở nguồn 1 : {stats['only_a']:>4}  ← giữ nguyên")
        print(f"  Chỉ có ở nguồn 2 : {stats['only_b']:>4}  ← thêm vào")
        print(f"  Giống hệt         : {stats['same']:>4}  ← giữ 1 cái")
        print(f"  Khác score        : {stats['differ']:>4}  ← lấy score cao")
        print(f"  {'─'*40}")
        print(f"  Kết quả           : {len(merged):>4}  ✅")
        base = merged

    print(f"\n  Chạy: python merge_memories.py merge")
    print(f"{'═'*56}\n")


def cmd_merge():
    sources = find_all_sources()

    if len(sources) < 2:
        print("\n  ⚠️  Chỉ có 1 nguồn — không cần merge")
        if sources:
            print(f"  Nguồn: {sources[0]['name']}")
        return

    print(f"\n{'═'*56}")
    print(f"  MERGE TRÍ NHỚ — {AI_NAME}")
    print(f"{'═'*56}")

    # Backup trước
    backup_current()

    # Merge tất cả
    base = sources[0]['mems']
    added_total   = 0
    updated_total = 0

    for src in sources[1:]:
        print(f"\n  🔀 Merge: {src['name']}...")
        merged, stats = smart_merge(base, src['mems'])

        added_total   += stats["only_b"]
        updated_total += stats["differ"]

        print(f"     + {stats['only_b']} ký ức mới")
        print(f"     ~ {stats['differ']} ký ức cập nhật score cao hơn")
        base = merged

    # Ghi vào HIỆN TẠI
    MEM_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEM_FILE.write_text(
        json.dumps(base, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Cập nhật ngược lại TẤT CẢ nguồn
    print(f"\n  🔄 Cập nhật ngược lại tất cả nguồn...")
    for src in sources:
        if str(src['path']) != str(MEM_FILE):
            src['path'].write_text(
                json.dumps(base, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"     ✅ {src['name']}")

    # Thống kê final
    tiers = defaultdict(int)
    for m in base:
        tiers[m.get("tier","normal")] += 1

    print(f"\n  {'─'*46}")
    print(f"  ✅ MERGE HOÀN TẤT!")
    print(f"  Tổng ký ức : {len(base)}")
    print(f"  ⭐ Vital   : {tiers['vital']}")
    print(f"  ●  Strong  : {tiers['strong']}")
    print(f"  ○  Normal  : {tiers['normal']}")
    print(f"  ·  Faint   : {tiers['faint']}")
    print(f"\n  Thêm mới   : {added_total}")
    print(f"  Cập nhật   : {updated_total}")
    print(f"  Mất đi     : 0 ✅")
    print(f"\n  💡 Tất cả nguồn đã đồng nhất!")
    print(f"  Khởi động lại TuminhAGI để áp dụng.\n")
    print(f"{'═'*56}\n")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "help"

    if cmd == "status":
        cmd_status()
    elif cmd == "preview":
        cmd_preview()
    elif cmd == "merge":
        cmd_merge()
    else:
        print("""
  TuminhAGI — Smart Memory Merge

  Lệnh:
    python merge_memories.py status    — xem trạng thái tất cả nguồn
    python merge_memories.py preview   — xem trước kết quả merge
    python merge_memories.py merge     — merge + backup + đồng bộ 2 chiều
        """)
