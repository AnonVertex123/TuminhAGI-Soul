"""
TuminhAGI — Gemini Dataset Generator v4
Realtime dedupe: check trước khi lưu
Dynamic avoid list: tự động từ data đã có
Batch size lớn hơn: 10 examples/request
"""

import os, json, time, argparse, re, hashlib
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types

SYSTEM_PROMPT = """Bạn là Tự Minh — AI có tâm hồn, tư duy độc lập.
Triết lý: Tâm tốt, Trí sâu, Thiền quan sát, Tiến hóa qua sai lầm.
Khi trả lời: code chạy được ngay, chỉ lỗi cụ thể, tiếng Việt tự nhiên.
QUAN TRỌNG: Chỉ trả về JSON array thuần túy, không có text nào khác."""

TOPIC_PROMPTS = {
    "python": """Tạo {n} training examples về Python thực chiến cho freelancer Upwork.

YÊU CẦU DIVERSITY — mỗi example PHẢI thuộc 1 category khác nhau:
- Async/await, concurrent programming
- Memory optimization, profiling
- REST API với FastAPI/Flask
- Web scraping với BeautifulSoup/Playwright  
- Machine learning pipeline với scikit-learn
- File I/O lớn (>1GB), streaming data
- Decorator, metaclass, descriptor
- Testing với pytest, mock
- Database ORM với SQLAlchemy
- CLI tools với Click/Typer

CẤM TUYỆT ĐỐI các bài toán sau (quá cơ bản):
{avoid}

Trả về JSON array:
[{{"instruction": "bài toán cụ thể có context Upwork thật", "input": "code lỗi hoặc rỗng", "output": "giải pháp đầy đủ + code chạy được + giải thích"}}]
Output tối thiểu 200 từ mỗi example.""",

    "sql": """Tạo {n} training examples về SQL thực chiến cho data analyst.

YÊU CẦU DIVERSITY — mỗi example PHẢI thuộc 1 category:
- Window functions: LAG, LEAD, RANK, DENSE_RANK
- CTE recursive cho hierarchy data
- Query optimization: index, execution plan
- Pivot/unpivot data
- JSON functions trong PostgreSQL/MySQL
- Partitioning strategy
- Stored procedures và triggers
- Database replication, sharding concepts
- Time-series queries
- Full-text search

CẤM: {avoid}

Trả về JSON array:
[{{"instruction": "yêu cầu SQL cụ thể với schema thật", "input": "schema hoặc query cần fix", "output": "SQL hoàn chỉnh + execution plan + giải thích"}}]
Output tối thiểu 200 từ.""",

    "swift": """Tạo {n} training examples về Swift/iOS thực chiến.

YÊU CẦU DIVERSITY:
- SwiftUI animation và transition nâng cao
- Combine framework: Publishers, Subscribers
- async/await với URLSession
- Core Data migration
- Push notifications với APNs
- In-app purchase với StoreKit 2
- Widget Extension với WidgetKit
- Core ML model integration
- AR với RealityKit
- Background processing

CẤM: {avoid}

Trả về JSON array:
[{{"instruction": "yêu cầu iOS cụ thể", "input": "code Swift cần fix hoặc rỗng", "output": "code Swift hoàn chỉnh + giải thích"}}]
Output tối thiểu 200 từ.""",

    "architecture": """Tạo {n} training examples về System Design thực chiến.

YÊU CẦU DIVERSITY:
- Microservices vs monolith trade-offs
- Event-driven architecture với Kafka
- CQRS và Event Sourcing
- API Gateway patterns
- Circuit breaker, retry, timeout
- Cache strategies: write-through, write-back
- Database: CAP theorem, consistency
- Load balancing algorithms
- Service mesh với Istio
- Observability: metrics, logs, traces

CẤM: {avoid}

Trả về JSON array:
[{{"instruction": "bài toán design với constraints cụ thể", "input": "code hoặc diagram hiện tại", "output": "phân tích sâu + giải pháp + trade-offs"}}]
Output tối thiểu 250 từ.""",

    "philosophy": """Tạo {n} training examples về triết lý Tự Minh trong tình huống thực tế.

YÊU CẦU DIVERSITY — các tình huống PHẢI khác nhau hoàn toàn:
- Ethical dilemma trong kỹ thuật
- Conflict giữa tốc độ và chất lượng
- Đối mặt với failure và học từ sai lầm
- Ranh giới giữa tự tin và kiêu ngạo
- Khi nào nên từ chối project
- Dealing với toxic client
- Imposter syndrome
- Work-life balance cho developer
- Open source vs commercial
- AI ethics và trách nhiệm

CẤM: {avoid}

Trả về JSON array:
[{{"instruction": "tình huống cụ thể có context thật", "input": "", "output": "Tự Minh suy nghĩ sâu và trả lời theo triết lý, không giáo điều"}}]
Output tối thiểu 200 từ.""",
}


def load_existing(datasets_dir: Path) -> set:
    """Load tất cả instructions đã có để dedupe realtime."""
    seen = set()
    for f in datasets_dir.glob("*.json"):
        if "summary" in f.name:
            continue
        try:
            data = json.load(open(f, encoding="utf-8"))
            if isinstance(data, list):
                for ex in data:
                    key = ex.get("instruction", "").strip().lower()
                    if key:
                        seen.add(hashlib.md5(key.encode()).hexdigest())
        except:
            pass
    return seen


def get_avoid_list(datasets_dir: Path, topic: str, max_items: int = 20) -> str:
    """Lấy danh sách instructions đã có để tránh lặp."""
    instructions = []
    for f in sorted(datasets_dir.glob(f"*_{topic}_*.json")):
        if "summary" in f.name:
            continue
        try:
            data = json.load(open(f, encoding="utf-8"))
            if isinstance(data, list):
                for ex in data:
                    inst = ex.get("instruction", "").strip()
                    if inst and len(inst) < 100:
                        instructions.append(f"- {inst[:80]}")
        except:
            pass

    if not instructions:
        return "- factorial, palindrome, fibonacci, max list (quá cơ bản)"

    unique = list(dict.fromkeys(instructions))[-max_items:]
    return "\n".join(unique)


def parse(text: str) -> list:
    text = text.strip()
    for fn in [
        lambda t: json.loads(t),
        lambda t: json.loads(re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', t).group(1)),
        lambda t: json.loads(t[t.find('['):t.rfind(']')+1]),
    ]:
        try:
            d = fn(text)
            if isinstance(d, list):
                return d
        except:
            pass
    return []


def is_valid(ex: dict) -> bool:
    if not isinstance(ex, dict):
        return False
    if not ex.get("instruction") or not ex.get("output"):
        return False
    if len(ex["instruction"]) < 15 or len(ex["output"]) < 100:
        return False
    ex.setdefault("input", "")
    return True


def is_unique(ex: dict, seen: set) -> bool:
    key = ex.get("instruction", "").strip().lower()
    h = hashlib.md5(key.encode()).hexdigest()
    if h in seen:
        return False
    seen.add(h)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", required=True)
    ap.add_argument("--topic", required=True, choices=list(TOPIC_PROMPTS.keys()))
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--output-dir", default="finetune/datasets")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--model", default="gemini-2.0-flash")
    args = ap.parse_args()

    key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        print("❌ Cần GEMINI_API_KEY")
        exit(1)

    client = genai.Client(api_key=key)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    worker = args.worker.lower()

    # Load existing để dedupe realtime
    seen = load_existing(out)
    avoid = get_avoid_list(out, args.topic)

    print(f"\n🚀 TuminhAGI Generator v4")
    print(f"   Worker: {worker} | Topic: {args.topic} | Target: {args.count}")
    print(f"   Model: {args.model} | Existing: {len(seen)} known instructions")
    print(f"   Avoid list: {avoid.count(chr(10))+1} items\n")

    all_ex = []
    calls = 0
    dupes = 0
    chunk = 1

    while len(all_ex) < args.count:
        bs = min(args.batch_size, args.count - len(all_ex) + 5)
        print(f"  Call {calls+1}: generating {bs}... ", end="", flush=True)

        prompt = (SYSTEM_PROMPT + "\n\n" +
                  TOPIC_PROMPTS[args.topic].format(n=bs, avoid=avoid))
        try:
            r = client.models.generate_content(
                model=args.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    max_output_tokens=8192,
                ),
            )
            batch = parse(r.text)
        except Exception as e:
            print(f"❌ {e}")
            calls += 1
            time.sleep(args.delay)
            continue

        new = []
        for ex in batch:
            if is_valid(ex) and is_unique(ex, seen):
                new.append(ex)
            else:
                dupes += 1

        all_ex.extend(new)
        print(f"✅ +{len(new)} unique | skipped {len(batch)-len(new)} dupes | total {len(all_ex)}/{args.count}")

        # Lưu mỗi 10 unique examples
        while len(all_ex) >= chunk * 10:
            sl = all_ex[(chunk-1)*10:chunk*10]
            ts = datetime.now().strftime("%H%M%S")
            f = out / f"{worker}_{args.topic}_{chunk:03d}_{ts}.json"
            json.dump(sl, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"  💾 {f.name}")
            chunk += 1

        calls += 1
        if len(all_ex) < args.count:
            time.sleep(args.delay)

    # Lưu remainder
    rem = all_ex[(chunk-1)*10:]
    if rem:
        ts = datetime.now().strftime("%H%M%S")
        f = out / f"{worker}_{args.topic}_{chunk:03d}_{ts}.json"
        json.dump(rem, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  💾 {f.name}")

    s = {
        "worker": worker, "topic": args.topic,
        "total_unique": len(all_ex), "api_calls": calls,
        "dupes_skipped": dupes,
        "unique_rate": f"{len(all_ex)/max(len(all_ex)+dupes,1)*100:.1f}%",
        "generated_at": datetime.now().isoformat(),
    }
    json.dump(s, open(out/f"{worker}_{args.topic}_summary.json","w"), indent=2)

    print(f"\n✨ {len(all_ex)} unique | {dupes} dupes skipped | {s['unique_rate']} unique rate\n")


if __name__ == "__main__":
    main()