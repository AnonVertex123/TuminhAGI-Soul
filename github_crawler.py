"""
TuminhAGI — GitHub Crawler
Crawl code thật từ GitHub public repos → convert thành training examples

Cách dùng:
  python github_crawler.py --language python --count 200
  python github_crawler.py --language swift --count 100 --token YOUR_GITHUB_TOKEN
  python github_crawler.py --language sql --count 100

Không cần GitHub token nhưng có token thì nhanh hơn (5000 req/hr vs 60 req/hr)
"""

import os
import json
import time
import argparse
import ast
import re
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# ─── CONFIG ──────────────────────────────────────────────────────────────────

QUALITY_FILTERS = {
    "min_stars": 500,
    "min_function_lines": 5,
    "max_function_lines": 80,
    "min_docstring_words": 10,
    "licenses": ["mit", "apache-2.0", "bsd-2-clause", 
                 "bsd-3-clause", "unlicense", "other", 
                 "cc-by-4.0", "lgpl-3.0", "gpl-3.0"],
}

SEARCH_QUERIES = {
    "python": [
        "language:python stars:>500 topic:python-library",
        "language:python stars:>200 topic:flask",
        "language:python stars:>200 topic:fastapi",
        "language:python stars:>200 topic:pandas",
        "language:python stars:>200 topic:scikit-learn",
        "language:python stars:>100 topic:pytest",
        "language:python stars:>300 topic:sqlalchemy",
        "language:python stars:>200 topic:celery",
        "language:python stars:>100 topic:click",
        "language:python stars:>200 topic:pydantic",
    ],
    "swift": [
        "language:swift stars:>1000 topic:swiftui",
        "language:swift stars:>500 topic:combine",
        "language:swift stars:>500 topic:swift-package-manager",
    ],
    "sql": [
        "language:sql stars:>100 license:mit",
        "topic:sql stars:>200 license:mit",
        "topic:postgresql stars:>300 license:mit",
    ],
    "javascript": [
        "language:javascript stars:>1000 license:mit topic:nodejs",
        "language:javascript stars:>500 license:mit topic:react",
    ],
}

# ─── GITHUB API ──────────────────────────────────────────────────────────────

def github_request(url: str, token: str = None) -> dict:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TuminhAGI-Crawler/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        if e.code == 403:
            print(f"  ⚠️  Rate limit hit, waiting 60s...")
            time.sleep(60)
        elif e.code == 404:
            return {}
        return {}
    except Exception as e:
        print(f"  ⚠️  Request error: {e}")
        return {}


def search_repos(query: str, token: str = None, per_page: int = 10) -> list:
    params = urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": per_page})
    url = f"https://api.github.com/search/repositories?{params}"
    data = github_request(url, token)
    return data.get("items", [])


def get_repo_contents(owner: str, repo: str, path: str = "", token: str = None) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    data = github_request(url, token)
    if isinstance(data, list):
        return data
    return []


def get_file_content(download_url: str, token: str = None) -> str:
    try:
        headers = {"User-Agent": "TuminhAGI-Crawler/1.0"}
        if token:
            headers["Authorization"] = f"token {token}"
        req = Request(download_url, headers=headers)
        with urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="ignore")
            return content
    except Exception:
        return ""


# ─── PYTHON PARSER ───────────────────────────────────────────────────────────

def extract_python_functions(code: str) -> list:
    functions = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Bỏ qua private functions và test functions
        if node.name.startswith("_") or node.name.startswith("test_"):
            continue

        # Lấy docstring
        docstring = ast.get_docstring(node)
        if not docstring or len(docstring.split()) < QUALITY_FILTERS["min_docstring_words"]:
            continue

        # Lấy source code
        try:
            lines = code.split("\n")
            start = node.lineno - 1
            end = node.end_lineno
            func_lines = lines[start:end]
            func_code = "\n".join(func_lines)
        except Exception:
            continue

        # Filter theo số dòng
        line_count = len(func_lines)
        if not (QUALITY_FILTERS["min_function_lines"] <= line_count <= QUALITY_FILTERS["max_function_lines"]):
            continue

        # Lấy type hints nếu có
        has_types = any(":" in line or "->" in line for line in func_lines[:3])

        functions.append({
            "name": node.name,
            "code": func_code,
            "docstring": docstring,
            "lines": line_count,
            "has_types": has_types,
        })

    return functions


def python_to_example(func: dict, repo_name: str) -> dict:
    instruction = f"Giải thích và cải thiện hàm `{func['name']}` trong Python."
    if func["has_types"]:
        instruction = f"Review hàm `{func['name']}` có type hints — tìm lỗi tiềm ẩn và đề xuất cải thiện."

    output = f"""Phân tích hàm `{func['name']}`:

**Mục đích:** {func['docstring'][:200]}

**Code hiện tại ({func['lines']} dòng):**
```python
{func['code']}
```

**Nhận xét của Tự Minh:**
- Code {'có type hints tốt' if func['has_types'] else 'chưa có type hints — nên thêm vào'}
- Độ phức tạp: {'đơn giản' if func['lines'] < 20 else 'trung bình' if func['lines'] < 50 else 'phức tạp'}
- Từ repo {repo_name} — code production thật

**Gợi ý cải thiện:**
1. Thêm error handling cho edge cases
2. {'Type hints đã có — kiểm tra return type' if func['has_types'] else 'Thêm type hints để code rõ ràng hơn'}
3. Viết unit test với pytest để đảm bảo correctness"""

    return {
        "instruction": instruction,
        "input": func["code"],
        "output": output,
        "source": "github",
        "repo": repo_name,
    }


# ─── SWIFT PARSER ────────────────────────────────────────────────────────────

def extract_swift_functions(code: str) -> list:
    functions = []
    pattern = r'(///.*?\n)*\s*(public|private|internal|open)?\s*(func|class func|static func)\s+(\w+)[^{]*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'

    for match in re.finditer(pattern, code, re.MULTILINE | re.DOTALL):
        comment = match.group(1) or ""
        func_name = match.group(4)
        func_body = match.group(5)
        full_func = match.group(0)

        if func_name.startswith("test") or func_name.startswith("_"):
            continue

        lines = full_func.split("\n")
        if not (QUALITY_FILTERS["min_function_lines"] <= len(lines) <= QUALITY_FILTERS["max_function_lines"]):
            continue

        doc = comment.replace("///", "").strip()
        if len(doc.split()) < 5:
            continue

        functions.append({
            "name": func_name,
            "code": full_func[:500],
            "docstring": doc[:200],
            "lines": len(lines),
        })

    return functions


def swift_to_example(func: dict, repo_name: str) -> dict:
    return {
        "instruction": f"Review và giải thích hàm Swift `{func['name']}` — tìm vấn đề và đề xuất cải thiện.",
        "input": func["code"],
        "output": f"""Phân tích hàm Swift `{func['name']}`:

**Mục đích:** {func['docstring']}

**Review của Tự Minh:**
```swift
{func['code']}
```

**Nhận xét:**
- Hàm {func['lines']} dòng — {'ngắn gọn tốt' if func['lines'] < 20 else 'có thể refactor'}
- Từ repo production {repo_name}
- Kiểm tra: memory management, optionals handling, error propagation

**Cải thiện:**
1. Thêm guard statements cho optional unwrapping
2. Sử dụng Result<T, Error> thay vì throws nếu phù hợp
3. Thêm /// documentation comments đầy đủ hơn""",
        "source": "github",
        "repo": repo_name,
    }


# ─── CRAWLER ─────────────────────────────────────────────────────────────────

def crawl_repo(owner: str, repo: str, language: str, token: str = None) -> list:
    examples = []
    contents = get_repo_contents(owner, repo, "", token)
    time.sleep(0.5)

    # Tìm files phù hợp (không đi sâu quá 1 level)
    extensions = {"python": ".py", "swift": ".swift", "sql": ".sql", "javascript": ".js"}
    ext = extensions.get(language, ".py")

    files = []
    for item in contents:
        if item.get("type") == "file" and item.get("name", "").endswith(ext):
            files.append(item)
        elif item.get("type") == "dir" and item.get("name") not in [".git", "test", "tests", "node_modules", "vendor"]:
            sub = get_repo_contents(owner, repo, item["path"], token)
            for sub_item in sub:
                if sub_item.get("type") == "file" and sub_item.get("name", "").endswith(ext):
                    files.append(sub_item)
            time.sleep(0.3)

    # Parse files
    for file_item in files[:5]:  # Max 5 files per repo
        download_url = file_item.get("download_url")
        if not download_url:
            continue

        content = get_file_content(download_url, token)
        if not content or len(content) > 100000:  # Skip files > 100KB
            continue

        repo_name = f"{owner}/{repo}"
        if language == "python":
            funcs = extract_python_functions(content)
            for func in funcs[:3]:  # Max 3 functions per file
                ex = python_to_example(func, repo_name)
                examples.append(ex)
        elif language == "swift":
            funcs = extract_swift_functions(content)
            for func in funcs[:3]:
                ex = swift_to_example(func, repo_name)
                examples.append(ex)

        time.sleep(0.5)

    return examples


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TuminhAGI GitHub Crawler")
    parser.add_argument("--language", required=True,
                        choices=list(SEARCH_QUERIES.keys()),
                        help="Language to crawl")
    parser.add_argument("--count", type=int, default=100,
                        help="Target number of examples")
    parser.add_argument("--output-dir", default="finetune/datasets")
    parser.add_argument("--token", default=None,
                        help="GitHub token (optional, increases rate limit)")
    parser.add_argument("--worker", default="github")
    args = parser.parse_args()

    # GitHub Token prioritize: arg > env
    token = args.token or os.getenv("GITHUB_TOKEN")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🕷️  TuminhAGI GitHub Crawler")
    print(f"   Language: {args.language} | Target: {args.count} examples")
    print(f"   Token: {'✅ có' if token else '❌ không có (rate limit 60/hr)'}")

    # Load existing để dedupe
    seen = set()
    for f in output_dir.glob("*.json"):
        if "summary" in f.name:
            continue
        try:
            data = json.load(open(f, encoding="utf-8"))
            if isinstance(data, list):
                for ex in data:
                    key = ex.get("instruction", "").strip().lower()
                    seen.add(hashlib.md5(key.encode()).hexdigest())
        except:
            pass

    print(f"   Existing: {len(seen)} known instructions\n")

    all_examples = []
    queries = SEARCH_QUERIES[args.language]
    chunk = 1

    for query in queries:
        if len(all_examples) >= args.count:
            break

        print(f"🔍 Query: {query}")
        repos = search_repos(query, token, per_page=10)
        print(f"   Found {len(repos)} repos")
        time.sleep(1)

        for repo in repos:
            if len(all_examples) >= args.count:
                break

            owner = repo["owner"]["login"]
            name = repo["name"]
            stars = repo["stargazers_count"]
            license_key = repo.get("license", {})
            if license_key:
                license_key = license_key.get("key", "")

            if license_key not in QUALITY_FILTERS["licenses"]:
                print(f"   ⏭️  {owner}/{name} — license {license_key} không phù hợp")
                continue

            print(f"   📦 {owner}/{name} ({stars}⭐) ", end="", flush=True)

            examples = crawl_repo(owner, name, args.language, token)

            # Dedupe
            new = []
            for ex in examples:
                key = ex.get("instruction", "").strip().lower()
                h = hashlib.md5(key.encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    new.append(ex)

            all_examples.extend(new)
            print(f"→ +{len(new)} examples | total: {len(all_examples)}/{args.count}")

            # Lưu mỗi 20 examples
            while len(all_examples) >= chunk * 20:
                sl = all_examples[(chunk-1)*20:chunk*20]
                ts = datetime.now().strftime("%H%M%S")
                fname = output_dir / f"{args.worker}_{args.language}_{chunk:03d}_{ts}.json"
                json.dump(sl, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"  💾 {fname.name}")
                chunk += 1

            time.sleep(1)

    # Lưu remainder
    rem = all_examples[(chunk-1)*20:]
    if rem:
        ts = datetime.now().strftime("%H%M%S")
        fname = output_dir / f"{args.worker}_{args.language}_{chunk:03d}_{ts}.json"
        json.dump(rem, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  💾 {fname.name}")

    # Summary
    summary = {
        "worker": args.worker,
        "language": args.language,
        "total": len(all_examples),
        "source": "github",
        "generated_at": datetime.now().isoformat(),
    }
    with open(output_dir / f"{args.worker}_{args.language}_github_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n✨ Xong! {len(all_examples)} examples từ GitHub")
    print(f"   100% code thật từ production repos!")
    print(f"   Chất lượng cao hơn Gemini generated data!\n")


if __name__ == "__main__":
    main()
