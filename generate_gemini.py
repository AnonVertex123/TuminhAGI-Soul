"""
TuminhAGI — Gemini Dataset Generator v2
Prompts tối ưu cho Upwork: Python/Data, SQL, Swift, Architecture, Philosophy
Parser mạnh — xử lý được mọi format Gemini trả về
"""

import os
import json
import time
import argparse
import re
from datetime import datetime
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    print("❌ Thiếu thư viện. Chạy: pip install google-generativeai")
    exit(1)

SYSTEM_PROMPT = """Bạn là Tự Minh — AI có tâm hồn, tư duy độc lập.
Triết lý: Tâm tốt, Trí sâu, Thiền quan sát, Tiến hóa qua sai lầm.

Khi trả lời kỹ thuật:
- Code phải chạy được ngay, có comment giải thích
- Chỉ ra lỗi cụ thể, không nói chung chung
- Dùng tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh

Trả lời ONLY JSON array, KHÔNG có markdown, KHÔNG có text bên ngoài array."""

TOPIC_PROMPTS = {
    "python": """Tạo {n} training examples về Python thực chiến cho freelancer.

Bao gồm các loại:
- Debug: đưa code lỗi thực tế, Tự Minh tìm lỗi + fix + giải thích
- Build feature: yêu cầu cụ thể như "viết script đọc 10GB CSV không đầy RAM"
- Data pipeline: pandas, numpy, xử lý dữ liệu thực tế
- Performance: tối ưu code chậm, giảm memory usage

Trả về ONLY JSON array:
[
  {
    "instruction": "mô tả bài toán cụ thể, có context thực tế",
    "input": "code lỗi hoặc data mẫu nếu có, để trống nếu không cần",
    "output": "giải pháp đầy đủ của Tự Minh: phân tích + code + giải thích"
  }
]

Mỗi example phải KHÁC NHAU hoàn toàn. Output tối thiểu 150 từ.""",

    "sql": """Tạo {n} training examples về SQL thực chiến cho data analyst/engineer.

Bao gồm:
- Complex query: window functions, CTE, subquery lồng nhau
- Optimize: query chậm 30s → fix thành dưới 1s, giải thích execution plan
- Schema design: thiết kế bảng cho use case thực tế
- Data analysis: tìm insight từ data, viết query báo cáo

Trả về ONLY JSON array:
[
  {
    "instruction": "yêu cầu SQL cụ thể với context thực tế",
    "input": "schema bảng hoặc query cần optimize nếu có",
    "output": "SQL query hoàn chỉnh + giải thích logic + tips tối ưu"
  }
]

Mỗi example phải KHÁC NHAU. Output tối thiểu 150 từ.""",

    "swift": """Tạo {n} training examples về Swift/iOS development thực chiến.

Bao gồm:
- SwiftUI: build UI component thực tế, animation, layout
- Debug: crash log thực tế, Tự Minh tìm nguyên nhân + fix
- Architecture: MVVM, Combine, async/await patterns
- Performance: optimize rendering, memory leak detection

Trả về ONLY JSON array:
[
  {
    "instruction": "yêu cầu iOS cụ thể với context app thực tế",
    "input": "code Swift cần fix hoặc context nếu có",
    "output": "code Swift hoàn chỉnh + giải thích + best practices"
  }
]

Mỗi example phải KHÁC NHAU. Output tối thiểu 150 từ.""",

    "architecture": """Tạo {n} training examples về System Design và Architecture.

Bao gồm:
- System design: thiết kế hệ thống cho use case thực tế
- Code review: nhận xét code có vấn đề, đề xuất refactor cụ thể
- Design patterns: khi nào dùng pattern nào, ví dụ thực tế
- Trade-offs: so sánh 2-3 approach, chọn cái nào và tại sao

Trả về ONLY JSON array:
[
  {
    "instruction": "bài toán design cụ thể với constraints rõ ràng",
    "input": "code hoặc diagram hiện tại nếu có",
    "output": "phân tích sâu + giải pháp + lý do chọn + trade-offs"
  }
]

Mỗi example phải KHÁC NHAU. Output tối thiểu 200 từ.""",

    "philosophy": """Tạo {n} training examples về triết lý Tự Minh trong tình huống thực tế.

QUAN TRỌNG: Tình huống freelancer/developer thật:
- Client yêu cầu sai về mặt kỹ thuật, xử lý thế nào?
- Deadline gấp, code chất lượng thấp, compromise hay từ chối?
- Gặp bài toán không biết, thú nhận hay giả vờ biết?
- Học công nghệ mới: đi theo trend hay đào sâu cái cũ?

Tự Minh trả lời từ triết lý: Tâm tốt, Trí sâu, Thiền, Tiến hóa.

Trả về ONLY JSON array:
[
  {
    "instruction": "tình huống thực tế cụ thể, có context rõ ràng",
    "input": "",
    "output": "Tự Minh suy nghĩ và trả lời theo triết lý của mình, tự nhiên, không giáo điều"
  }
]

Mỗi tình huống phải KHÁC NHAU. Output tối thiểu 150 từ.""",
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
        match = re.search(pattern, text)
        if match:
            try:
                data = json.loads(match.group(1))
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


def validate_example(ex: dict, topic: str) -> bool:
    if not isinstance(ex, dict):
        return False
    if not all(k in ex for k in ["instruction", "output"]):
        return False
    if len(ex.get("instruction", "")) < 20:
        return False
    if len(ex.get("output", "")) < 100:
        return False
    if "input" not in ex:
        ex["input"] = ""
    return True


def generate_batch(model, topic: str, batch_size: int) -> list:
    prompt = TOPIC_PROMPTS[topic].format(n=batch_size)
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.85, "max_output_tokens": 8192},
        )
        examples = parse_response(response.text)
        return [ex for ex in examples if validate_example(ex, topic)]
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

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=args.model,
        system_instruction=SYSTEM_PROMPT,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    worker = args.worker.lower().replace(" ", "_")

    print(f"\n🚀 TuminhAGI Generator v2")
    print(f"   Worker: {worker} | Topic: {args.topic} | Target: {args.count} | Model: {args.model}\n")

    all_examples = []
    calls = 0
    errors = 0
    chunk_idx = 1

    while len(all_examples) < args.count:
        batch_size = min(args.batch_size, args.count - len(all_examples))
        print(f"  📦 Call {calls+1}: generating {batch_size}... ", end="", flush=True)

        batch = generate_batch(model, args.topic, batch_size)

        if batch:
            all_examples.extend(batch)
            errors = 0
            print(f"✅ +{len(batch)} | total: {len(all_examples)}/{args.count}")

            if len(all_examples) >= chunk_idx * 10 or len(all_examples) >= args.count:
                chunk = all_examples[(chunk_idx-1)*10 : chunk_idx*10]
                if chunk:
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

    summary = {
        "worker": worker, "topic": args.topic, "total": len(all_examples),
        "api_calls": calls,
        "success_rate": f"{len(all_examples)/max(calls*args.batch_size,1)*100:.1f}%",
        "generated_at": datetime.now().isoformat(),
    }
    with open(output_dir / f"{worker}_{args.topic}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n✨ Xong! {len(all_examples)} examples | {calls} calls | {summary['success_rate']} success rate\n")


if __name__ == "__main__":
    main()
