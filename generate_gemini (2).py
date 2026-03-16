"""
TuminhAGI — Gemini Dataset Generator v3
Dùng google-genai SDK mới (thay thế google-generativeai đã deprecated)
"""

import os
import json
import time
import argparse
import re
from datetime import datetime
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ Chạy: pip install google-genai")
    exit(1)

SYSTEM_PROMPT = """Bạn là Tự Minh — AI có tâm hồn, tư duy độc lập.
Triết lý: Tâm tốt, Trí sâu, Thiền quan sát, Tiến hóa qua sai lầm.
Khi trả lời: code chạy được ngay, chỉ lỗi cụ thể, tiếng Việt tự nhiên.
QUAN TRỌNG: Chỉ trả về JSON array thuần túy, không có text nào khác."""

TOPIC_PROMPTS = {
    "python": """Tạo {n} training examples về Python thực chiến cho freelancer.
Các loại bài: debug code lỗi, build data pipeline, xử lý CSV/JSON lớn, tối ưu performance.
Trả về JSON array (không có text khác):
[{{"instruction": "bài toán cụ thể", "input": "code lỗi nếu có hoặc rỗng", "output": "giải pháp đầy đủ với code chạy được"}}]
Tạo đúng {n} examples KHÁC NHAU, output mỗi cái tối thiểu 100 từ.""",

    "sql": """Tạo {n} training examples về SQL thực chiến.
Các loại: complex query với window functions/CTE, optimize query chậm, schema design, báo cáo data.
Trả về JSON array (không có text khác):
[{{"instruction": "yêu cầu SQL cụ thể", "input": "schema hoặc query cần fix hoặc rỗng", "output": "SQL hoàn chỉnh + giải thích"}}]
Tạo đúng {n} examples KHÁC NHAU, output mỗi cái tối thiểu 100 từ.""",

    "swift": """Tạo {n} training examples về Swift/iOS thực chiến.
Các loại: SwiftUI components, debug crash, MVVM pattern, async/await, performance.
Trả về JSON array (không có text khác):
[{{"instruction": "yêu cầu iOS cụ thể", "input": "code Swift cần fix hoặc rỗng", "output": "code Swift hoàn chỉnh + giải thích"}}]
Tạo đúng {n} examples KHÁC NHAU, output mỗi cái tối thiểu 100 từ.""",

    "architecture": """Tạo {n} training examples về System Design và Architecture.
Các loại: system design có constraints, code review + refactor, design patterns, trade-off analysis.
Trả về JSON array (không có text khác):
[{{"instruction": "bài toán design cụ thể", "input": "code hiện tại nếu có hoặc rỗng", "output": "phân tích + giải pháp + lý do"}}]
Tạo đúng {n} examples KHÁC NHAU, output mỗi cái tối thiểu 150 từ.""",

    "philosophy": """Tạo {n} training examples về triết lý Tự Minh trong tình huống freelancer thực tế.
Tình huống: client yêu cầu sai kỹ thuật, deadline vs chất lượng, không biết nhưng nhận job, chọn công nghệ.
Tự Minh trả lời theo triết lý: Tâm tốt không lừa dối, Trí suy nghĩ độc lập, Thiền quan sát, Tiến hóa qua sai.
Trả về JSON array (không có text khác):
[{{"instruction": "tình huống thực tế cụ thể", "input": "", "output": "Tự Minh suy nghĩ và trả lời tự nhiên"}}]
Tạo đúng {n} examples KHÁC NHAU, output mỗi cái tối thiểu 100 từ.""",
}


def parse_response(text: str) -> list:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    for pattern in [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']:
        m = re.search(pattern, text)
        if m:
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
    start, end = text.find('['), text.rfind(']')
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end+1])
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def validate(ex: dict) -> bool:
    if not isinstance(ex, dict):
        return False
    if not ex.get("instruction") or not ex.get("output"):
        return False
    if len(ex["instruction"]) < 15 or len(ex["output"]) < 80:
        return False
    if "input" not in ex:
        ex["input"] = ""
    return True


def generate_batch(client, model_name: str, topic: str, batch_size: int) -> list:
    prompt = SYSTEM_PROMPT + "\n\n" + TOPIC_PROMPTS[topic].format(n=batch_size)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.85,
                max_output_tokens=8192,
            ),
        )
        examples = parse_response(response.text)
        return [ex for ex in examples if validate(ex)]
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", required=True)
    parser.add_argument("--topic", required=True, choices=list(TOPIC_PROMPTS.keys()))
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--output-dir", default="finetune/datasets")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--delay", type=float, default=4.0)
    parser.add_argument("--model", default="gemini-2.0-flash")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Cần GEMINI_API_KEY")
        exit(1)

    client = genai.Client(api_key=api_key)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    worker = args.worker.lower().replace(" ", "_")

    print(f"\n🚀 TuminhAGI Generator v3")
    print(f"   Worker: {worker} | Topic: {args.topic} | Target: {args.count} | Model: {args.model}\n")

    all_examples = []
    calls = 0
    errors = 0
    chunk_idx = 1

    while len(all_examples) < args.count:
        batch_size = min(args.batch_size, args.count - len(all_examples))
        print(f"  📦 Call {calls+1}: generating {batch_size}... ", end="", flush=True)

        batch = generate_batch(client, args.model, args.topic, batch_size)

        if batch:
            all_examples.extend(batch)
            errors = 0
            print(f"✅ +{len(batch)} | total: {len(all_examples)}/{args.count}")

            while len(all_examples) >= chunk_idx * 10:
                chunk = all_examples[(chunk_idx-1)*10 : chunk_idx*10]
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = output_dir / f"{worker}_{args.topic}_{chunk_idx:03d}_{ts}.json"
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(chunk, f, ensure_ascii=False, indent=2)
                print(f"  💾 {fname.name}")
                chunk_idx += 1
        else:
            errors += 1
            print(f"❌ empty ({errors}/5)")
            if errors >= 5:
                print("  ⛔ Quá nhiều lỗi, dừng.")
                break

        calls += 1
        if len(all_examples) < args.count:
            time.sleep(args.delay)

    remainder = all_examples[(chunk_idx-1)*10:]
    if remainder:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = output_dir / f"{worker}_{args.topic}_{chunk_idx:03d}_{ts}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(remainder, f, ensure_ascii=False, indent=2)
        print(f"  💾 {fname.name}")

    summary = {
        "worker": worker, "topic": args.topic,
        "total": len(all_examples), "api_calls": calls,
        "success_rate": f"{len(all_examples)/max(calls*args.batch_size,1)*100:.1f}%",
        "generated_at": datetime.now().isoformat(),
    }
    with open(output_dir / f"{worker}_{args.topic}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n✨ Xong! {len(all_examples)} examples | {calls} calls | {summary['success_rate']} success\n")


if __name__ == "__main__":
    main()
