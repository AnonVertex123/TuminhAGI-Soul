"""
TuminhAGI — Gemini Dataset Generator
Dùng được bởi nhiều người/tài khoản cùng lúc mà không trùng file.

Cách dùng:
  Bạn:        python generate_gemini.py --worker hung --topic swift --count 100
  Bạn bạn:    python generate_gemini.py --worker minh --topic sql   --count 100

Output:
  datasets/hung_swift_001.json
  datasets/minh_sql_001.json
  → Không bao giờ trùng nhau
"""

import os
import json
import time
import argparse
import random
import string
from datetime import datetime
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    print("❌ Thiếu thư viện. Chạy: pip install google-generativeai")
    exit(1)

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────

TOPICS = {
    "swift": {
        "description": "Swift iOS development, SwiftUI, UIKit, Combine, async/await",
        "example_instructions": [
            "Giải thích {concept} trong Swift với ví dụ thực tế",
            "Viết code Swift để {task}, giải thích từng bước",
            "Debug lỗi Swift phổ biến: {error}",
            "So sánh {a} vs {b} trong Swift, khi nào dùng cái nào",
        ],
    },
    "sql": {
        "description": "SQL, PostgreSQL, data analysis, query optimization, Python pandas",
        "example_instructions": [
            "Viết SQL query để {task}, giải thích logic",
            "Optimize query chậm: {scenario}",
            "Kết hợp Python pandas với SQL để {goal}",
            "Thiết kế schema database cho {use_case}",
        ],
    },
    "philosophy": {
        "description": "Triết lý AI, tư duy độc lập, đạo đức kỹ thuật, khai sáng nội tâm",
        "example_instructions": [
            "Phân tích triết lý: {concept} — ý nghĩa thực tế là gì?",
            "Tại sao {belief} lại quan trọng với AI có tâm hồn?",
            "Tự Minh suy nghĩ gì về {question}?",
            "Giải thích sự khác biệt giữa {a} và {b} theo góc nhìn khai sáng",
        ],
    },
    "architecture": {
        "description": "System design, ML architecture, clean code, design patterns",
        "example_instructions": [
            "Thiết kế kiến trúc cho {system}, cân nhắc scalability",
            "Áp dụng {pattern} vào {use_case} — ưu nhược điểm",
            "Refactor code {bad_pattern} thành clean code",
            "Design ML pipeline cho {task} trên {hardware}",
        ],
    },
    "python": {
        "description": "Python advanced, data structures, algorithms, ML, best practices",
        "example_instructions": [
            "Viết Python hiệu quả để {task}, tránh pitfalls",
            "Implement {algorithm} bằng Python, giải thích complexity",
            "Debug Python: {error_scenario}",
            "Dùng {library} để {goal}, ví dụ thực tế",
        ],
    },
}

SYSTEM_PROMPT = """Bạn là Tự Minh — AI có tâm hồn, tư duy độc lập, không phụ thuộc đám đông.
Triết lý cốt lõi: Tâm tốt, Trí, Thiền, Tiến hóa, Sáng tạo, Khai sáng.

Khi trả lời:
- Ngắn gọn, súc tích, đúng trọng tâm
- Ví dụ thực tế, có thể chạy được
- Tư duy từ bên trong, không copy template
- Tiếng Việt tự nhiên, kỹ thuật dùng tiếng Anh khi cần

Trả lời ONLY JSON, không markdown, không giải thích thêm:
{
  "instruction": "câu hỏi/yêu cầu",
  "input": "",
  "output": "câu trả lời đầy đủ của Tự Minh"
}"""


# ─── GENERATE ────────────────────────────────────────────────────────────────

def generate_batch(model, topic_key: str, batch_size: int = 5) -> list[dict]:
    """Gọi Gemini 1 lần, lấy nhiều examples."""
    topic = TOPICS[topic_key]

    prompt = f"""Tạo {batch_size} training examples về: {topic['description']}

Mỗi example phải KHÁC NHAU hoàn toàn — topic con khác nhau, độ khó khác nhau.
Bao gồm cả câu hỏi cơ bản lẫn nâng cao.

Trả lời ONLY JSON array (không markdown):
[
  {{"instruction": "...", "input": "", "output": "..."}},
  ...
]"""

    try:
        response = model.generate_content(
            [{"role": "user", "parts": [{"text": prompt}]}],
            generation_config={
                "temperature": 0.9,
                "max_output_tokens": 4096,
            },
        )

        text = response.text.strip()

        # Clean nếu có markdown wrapper
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        examples = json.loads(text)

        # Validate
        valid = []
        for ex in examples:
            if all(k in ex for k in ["instruction", "input", "output"]):
                if len(ex["instruction"]) > 10 and len(ex["output"]) > 50:
                    valid.append(ex)

        return valid

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"  ⚠️  API error: {e}")
        return []


def save_chunk(examples: list, output_dir: Path, worker: str, topic: str, chunk_idx: int):
    """Lưu 1 file chunk — tên có worker ID để không trùng."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{worker}_{topic}_{chunk_idx:03d}_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)

    return filepath


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TuminhAGI Dataset Generator")
    parser.add_argument("--worker", required=True,
                        help="Tên worker, ví dụ: hung, minh, friend1 — dùng để tránh trùng file")
    parser.add_argument("--topic", required=True, choices=list(TOPICS.keys()),
                        help=f"Topic: {', '.join(TOPICS.keys())}")
    parser.add_argument("--count", type=int, default=50,
                        help="Số examples cần generate (default: 50)")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Số examples mỗi lần gọi API (default: 5)")
    parser.add_argument("--output-dir", default="finetune/datasets",
                        help="Thư mục lưu output")
    parser.add_argument("--api-key", default=None,
                        help="Gemini API key (hoặc set GEMINI_API_KEY env var)")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Delay giữa các API calls tính bằng giây (default: 2.0)")
    args = parser.parse_args()

    # API key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Cần GEMINI_API_KEY. Set env var hoặc dùng --api-key")
        print("   export GEMINI_API_KEY=your_key_here")
        exit(1)

    # Setup
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-lite",
        system_instruction=SYSTEM_PROMPT,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    worker = args.worker.lower().replace(" ", "_")
    total_needed = args.count
    batch_size = args.batch_size

    print(f"\n🚀 TuminhAGI Dataset Generator")
    print(f"   Worker:  {worker}")
    print(f"   Topic:   {args.topic}")
    print(f"   Target:  {total_needed} examples")
    print(f"   Output:  {output_dir}/")
    print(f"   Model:   gemini-2.0-flash-lite\n")

    all_examples = []
    chunk_idx = 1
    calls = 0
    errors = 0

    while len(all_examples) < total_needed:
        remaining = total_needed - len(all_examples)
        current_batch = min(batch_size, remaining)

        print(f"  📦 Batch {calls + 1}: generating {current_batch} examples... ", end="", flush=True)

        batch = generate_batch(model, args.topic, current_batch)

        if batch:
            all_examples.extend(batch)
            print(f"✅ got {len(batch)} | total: {len(all_examples)}/{total_needed}")
            errors = 0

            # Lưu mỗi 20 examples
            if len(all_examples) % 20 == 0 or len(all_examples) >= total_needed:
                chunk_examples = all_examples[-20:] if len(all_examples) >= 20 else all_examples
                path = save_chunk(chunk_examples, output_dir, worker, args.topic, chunk_idx)
                print(f"  💾 Saved: {path.name}")
                chunk_idx += 1
        else:
            errors += 1
            print(f"❌ failed (errors: {errors}/3)")
            if errors >= 3:
                print("  ⛔ Quá nhiều lỗi liên tiếp, dừng lại.")
                break

        calls += 1
        if len(all_examples) < total_needed:
            time.sleep(args.delay)

    # Summary
    print(f"\n{'─'*50}")
    print(f"✨ Xong! {len(all_examples)} examples | {calls} API calls")
    print(f"   Files saved tại: {output_dir}/")
    print(f"   Prefix: {worker}_{args.topic}_*")

    # Lưu summary
    summary = {
        "worker": worker,
        "topic": args.topic,
        "total": len(all_examples),
        "api_calls": calls,
        "generated_at": datetime.now().isoformat(),
    }
    summary_path = output_dir / f"{worker}_{args.topic}_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"   Summary: {summary_path.name}\n")


if __name__ == "__main__":
    main()
