"""
TuminhAGI — Gemini Dataset Generator v3
"""
import os, json, time, argparse, re
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types

SYSTEM_PROMPT = "Bạn là Tự Minh. Chỉ trả về JSON array thuần túy, không text khác."

TOPIC_PROMPTS = {
    "python": 'Tạo {n} examples Python thực chiến. Trả về JSON array: [{{"instruction":"bài toán","input":"code lỗi hoặc rỗng","output":"giải pháp + code"}}]. Tạo {n} examples KHÁC NHAU.',
    "sql": 'Tạo {n} examples SQL thực chiến. Trả về JSON array: [{{"instruction":"yêu cầu SQL","input":"schema hoặc rỗng","output":"SQL + giải thích"}}]. Tạo {n} examples KHÁC NHAU.',
    "swift": 'Tạo {n} examples Swift/iOS thực chiến. Trả về JSON array: [{{"instruction":"yêu cầu iOS","input":"code cần fix hoặc rỗng","output":"code Swift + giải thích"}}]. Tạo {n} examples KHÁC NHAU.',
    "architecture": 'Tạo {n} examples System Design. Trả về JSON array: [{{"instruction":"bài toán design","input":"code hiện tại hoặc rỗng","output":"giải pháp + lý do"}}]. Tạo {n} examples KHÁC NHAU.',
    "philosophy": 'Tạo {n} examples triết lý Tự Minh trong tình huống freelancer thực tế. Trả về JSON array: [{{"instruction":"tình huống cụ thể","input":"","output":"Tự Minh trả lời theo triết lý"}}]. Tạo {n} examples KHÁC NHAU.',
}

def parse(text):
    text = text.strip()
    for fn in [
        lambda t: json.loads(t),
        lambda t: json.loads(re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', t).group(1)),
        lambda t: json.loads(t[t.find('['):t.rfind(']')+1]),
    ]:
        try:
            d = fn(text)
            if isinstance(d, list): return d
        except: pass
    return []

def ok(ex):
    if not isinstance(ex, dict): return False
    if not ex.get("instruction") or not ex.get("output"): return False
    if len(ex["instruction"]) < 10 or len(ex["output"]) < 50: return False
    ex.setdefault("input", "")
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", required=True)
    ap.add_argument("--topic", required=True, choices=list(TOPIC_PROMPTS.keys()))
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=5)
    ap.add_argument("--output-dir", default="finetune/datasets")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--model", default="gemini-2.0-flash")
    args = ap.parse_args()

    key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not key: print("❌ Cần GEMINI_API_KEY") or exit(1)

    client = genai.Client(api_key=key)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    worker = args.worker.lower()

    print(f"\n🚀 v3 | {worker} | {args.topic} | {args.count} examples | {args.model}\n")

    all_ex, calls, errs, chunk = [], 0, 0, 1

    while len(all_ex) < args.count:
        bs = min(args.batch_size, args.count - len(all_ex))
        print(f"  Call {calls+1}: {bs} examples... ", end="", flush=True)
        prompt = SYSTEM_PROMPT + "\n\n" + TOPIC_PROMPTS[args.topic].format(n=bs)
        try:
            r = client.models.generate_content(
                model=args.model, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.85, max_output_tokens=8192)
            )
            print(f"DEBUG RESPONSE: {r.text[:500]}")
            batch = [e for e in parse(r.text) if ok(e)]
        except Exception as e:
            print(f"❌ {e}"); batch = []

        if batch:
            all_ex.extend(batch); errs = 0
            print(f"✅ +{len(batch)} | total {len(all_ex)}/{args.count}")
            while len(all_ex) >= chunk * 10:
                sl = all_ex[(chunk-1)*10:chunk*10]
                f = out / f"{worker}_{args.topic}_{chunk:03d}_{datetime.now().strftime('%H%M%S')}.json"
                json.dump(sl, open(f,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"  💾 {f.name}"); chunk += 1
        else:
            errs += 1; print(f"❌ ({errs}/5)")
            if errs >= 5: print("⛔ Dừng."); break

        calls += 1
        if len(all_ex) < args.count: time.sleep(args.delay)

    rem = all_ex[(chunk-1)*10:]
    if rem:
        f = out / f"{worker}_{args.topic}_{chunk:03d}_{datetime.now().strftime('%H%M%S')}.json"
        json.dump(rem, open(f,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  💾 {f.name}")

    s = {"worker":worker,"topic":args.topic,"total":len(all_ex),"api_calls":calls,
         "success_rate":f"{len(all_ex)/max(calls*args.batch_size,1)*100:.1f}%",
         "generated_at":datetime.now().isoformat()}
    json.dump(s, open(out/f"{worker}_{args.topic}_summary.json","w"), indent=2)
    print(f"\n✨ {len(all_ex)} examples | {calls} calls | {s['success_rate']} success\n")

if __name__ == "__main__":
    main()