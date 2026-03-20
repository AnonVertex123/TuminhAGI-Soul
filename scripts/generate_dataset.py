from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    raise SystemExit(
        "Missing env `GEMINI_API_KEY`. Set it in GitHub Actions secrets."
    )

import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

INPUT_PATH = Path("data/raw/crawled.json")
OUTPUT_DIR = Path("data/generated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """Bạn là chuyên gia tạo dataset huấn luyện AI y tế.
Từ đoạn code/văn bản được cung cấp, hãy tạo 3 cặp (instruction, input, output)
theo định dạng JSON sau. Ưu tiên nội dung liên quan y tế, thuốc Nam, chẩn đoán.

Trả về JSON array, không có markdown, không giải thích thêm:
[
  {
    "instruction": "câu lệnh / yêu cầu cụ thể",
    "input": "ngữ cảnh hoặc dữ liệu đầu vào (có thể rỗng)",
    "output": "câu trả lời mẫu chất lượng cao",
    "source": "tên repo",
    "quality": 0.0
  }
]

Quy tắc:
- instruction phải rõ ràng, thực tế
- output phải đúng, an toàn về y tế
- quality: 0.0-1.0 (tự đánh giá chất lượng)
- Nếu nội dung không liên quan y tế/code hữu ích → trả về []
"""


def _parse_json_array(text: str) -> list:
    t = text.strip()
    if t.startswith("["):
        return json.loads(t)
    start = t.find("[")
    end = t.rfind("]")
    if start >= 0 and end > start:
        return json.loads(t[start : end + 1])
    return []


def generate_samples(sample: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = (sample.get("content") or "")[:3000]
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Nguồn: {sample.get('repo')}\n"
        f"Nội dung:\n{content}"
    )

    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        samples = _parse_json_array(text)
        if not isinstance(samples, list):
            return []

        # Thêm metadata (giữ nguyên format spec)
        for s in samples:
            if not isinstance(s, dict):
                continue
            s["source_repo"] = sample.get("repo")
            s["source_path"] = sample.get("path")
            s["topic"] = sample.get("topic")
        return samples
    except Exception as e:
        print(f"  [Gemini Error] {e}")
        return []


def generate() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"Missing input: {INPUT_PATH}")

    raw_samples = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_samples, list):
        raise SystemExit("crawled.json must be a list")

    print(f"[Generate] Processing {len(raw_samples)} files...")
    all_generated: List[Dict[str, Any]] = []

    for i, sample in enumerate(raw_samples):
        print(f"  [{i+1}/{len(raw_samples)}] {sample.get('repo')}/{sample.get('path')}")
        samples = generate_samples(sample)
        all_generated.extend(samples)

        time.sleep(1.5)  # Rate limit

        # Checkpoint mỗi 20 files
        if (i + 1) % 20 == 0:
            checkpoint_path = OUTPUT_DIR / f"checkpoint_{i+1}.json"
            checkpoint_path.write_text(
                json.dumps(all_generated, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [Checkpoint] Saved {len(all_generated)} samples")

    output_path = OUTPUT_DIR / "generated.json"
    output_path.write_text(
        json.dumps(all_generated, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[Generate] Done — {len(all_generated)} samples")


if __name__ == "__main__":
    generate()

