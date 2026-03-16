import os
import json
import time
import argparse
from pathlib import Path
from google import genai
from google.genai import types

def filter_data():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY"))
    parser.add_argument("--input-dir", default="finetune/datasets")
    parser.add_argument("--output-dir", default="finetune/vetted_datasets")
    parser.add_argument("--model", default="gemini-2.0-flash-lite")
    args = parser.parse_args()

    if not args.api_key:
        print("❌ Lỗi: Thiếu GEMINI_API_KEY")
        return

    client = genai.Client(api_key=args.api_key)
    input_path = Path(args.input_dir)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách files cào từ GitHub
    files = list(input_path.glob("github_*.json"))
    if not files:
        print("📂 Không tìm thấy file 'github_*.json' nào.")
        return

    print(f"🕵️  Bắt đầu AI Quality Review cho {len(files)} files...")

    prompt_template = """Bạn là Tự Minh — Chuyên gia kiểm định chất lượng mã nguồn (Quality Reviewer).
Nhiệm vụ: Đánh giá xem đoạn code production được cào từ GitHub sau đây có đủ tốt để làm tập học không.

TIÊU CHÍ (Chỉ duyệt nếu đạt TẤT CẢ):
1. Logic rõ ràng, không có bug nghiêm trọng.
2. Code sạch, có tính ứng dụng cao (không phải code rác, code test linh tinh).
3. Không chứa thông tin nhạy cảm (API Key, mật khẩu, thông tin cá nhân).
4. Phù hợp với chuẩn mực của TuminhAGI: Tâm tốt, Trí sâu.

EXAMPLE CẦN ĐÁNH GIÁ:
Instruction: {instruction}
Input: {input}
Output: {output}

TRẢ VỀ JSON:
{{"approved": true/false, "reason": "lý do ngắn gọn", "score": 0-100}}
"""

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
            
            vetted = []
            for ex in data:
                # Gọi Gemini review
                prompt = prompt_template.format(
                    instruction=ex.get("instruction", ""),
                    input=ex.get("input", ""),
                    output=ex.get("output", "")[:2000] # Limit context
                )
                
                try:
                    response = client.models.generate_content(
                        model=args.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                    result = json.loads(response.text)
                    
                    if result.get("approved"):
                        ex["ai_score"] = result.get("score")
                        vetted.append(ex)
                        print(f"  ✅ Approved: {ex['instruction'][:50]}... ({result['score']}/{result['reason']})")
                    else:
                        print(f"  ❌ Rejected: {ex['instruction'][:50]}... ({result['reason']})")
                except Exception as e:
                    print(f"  ⚠️  Lỗi review example: {e}")
                    # Backup: nếu lỗi API thì tạm thời bỏ qua example này để an toàn
                
                time.sleep(1) # Tránh rate limit
            
            if vetted:
                out_name = output_path / f"vetted_{f.name}"
                with open(out_name, "w", encoding="utf-8") as out_f:
                    json.dump(vetted, out_f, ensure_ascii=False, indent=2)
                print(f"💾 Đã lưu {len(vetted)}/{len(data)} examples đạt chuẩn vào {out_name.name}")
            
        except Exception as e:
            print(f"💥 Lỗi xử lý file {f.name}: {e}")

if __name__ == "__main__":
    filter_data()
