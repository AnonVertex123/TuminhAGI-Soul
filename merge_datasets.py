"""
TuminhAGI — Merge Datasets
Gom tất cả files từ nhiều workers thành 1 file training cuối cùng.

Cách dùng:
  python merge_datasets.py
  python merge_datasets.py --output final_train.json --shuffle
"""

import json
import argparse
import random
from pathlib import Path
from collections import defaultdict


def merge(input_dir: str = "finetune/datasets",
          output_file: str = "finetune/datasets/FINAL_train.json",
          shuffle: bool = True,
          dedupe: bool = True):

    input_path = Path(input_dir)
    files = sorted(input_path.glob("*.json"))

    # Bỏ qua summary files và file FINAL
    data_files = [f for f in files
                  if "summary" not in f.name and "FINAL" not in f.name]

    if not data_files:
        print(f"❌ Không tìm thấy file nào trong {input_dir}/")
        return

    print(f"\n📂 Tìm thấy {len(data_files)} files\n")

    all_examples = []
    stats = defaultdict(lambda: defaultdict(int))  # stats[worker][topic]

    for f in data_files:
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)

            if isinstance(data, list):
                # Parse worker + topic từ tên file: hung_swift_001_....json
                parts = f.stem.split("_")
                worker = parts[0] if len(parts) > 0 else "unknown"
                topic = parts[1] if len(parts) > 1 else "unknown"

                all_examples.extend(data)
                stats[worker][topic] += len(data)
                print(f"  ✅ {f.name}: {len(data)} examples")
        except Exception as e:
            print(f"  ⚠️  {f.name}: lỗi — {e}")

    print(f"\n📊 Tổng cộng: {len(all_examples)} examples trước dedupe\n")

    # Deduplicate theo instruction
    if dedupe:
        seen = set()
        unique = []
        dupes = 0
        for ex in all_examples:
            key = ex.get("instruction", "").strip().lower()[:100]
            if key not in seen:
                seen.add(key)
                unique.append(ex)
            else:
                dupes += 1
        print(f"🔍 Dedupe: xóa {dupes} trùng → còn {len(unique)} examples")
        all_examples = unique

    # Shuffle
    if shuffle:
        random.shuffle(all_examples)
        print(f"🔀 Shuffled")

    # Lưu
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_examples, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Saved: {output_path}")
    print(f"   Total examples: {len(all_examples)}")

    # In stats theo worker
    print(f"\n{'─'*40}")
    print("📈 Stats theo worker:")
    for worker, topics in stats.items():
        total = sum(topics.values())
        breakdown = ", ".join(f"{t}: {n}" for t, n in topics.items())
        print(f"  {worker:10} {total:4} examples  ({breakdown})")

    print(f"\n✨ FINAL_train.json sẵn sàng để fine-tune!\n")

    return len(all_examples)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="finetune/datasets")
    parser.add_argument("--output", default="finetune/datasets/FINAL_train.json")
    parser.add_argument("--shuffle", action="store_true", default=True)
    parser.add_argument("--no-dedupe", action="store_true")
    args = parser.parse_args()

    merge(
        input_dir=args.input_dir,
        output_file=args.output,
        shuffle=args.shuffle,
        dedupe=not args.no_dedupe,
    )
