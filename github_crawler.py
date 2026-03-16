"""
TuminhAGI — GitHub Crawler
Crawl code thật từ GitHub public repos → convert thành training examples

Cách dùng:
  python github_crawler.py --language python --count 200
  python github_crawler.py --language swift --count 100 --token YOUR_GITHUB_TOKEN
  python github_crawler.py --language swift --query "stars:>500 topic:swift-ui"
"""

import os
import sys
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

# ─── WINDOWS FIX ─────────────────────────────────────────────────────────────
if sys.platform == "win32":
    # Fix "Could not find platform independent libraries <prefix>"
    # Thường do PYTHONPATH hoặc PYTHONHOME không đồng bộ
    if "PYTHONHOME" not in os.environ:
        os.environ["PYTHONHOME"] = sys.prefix
    if "PYTHONPATH" not in os.environ:
        os.environ["PYTHONPATH"] = os.path.join(sys.prefix, "Lib")

# ─── CONFIG ──────────────────────────────────────────────────────────────────

QUALITY_FILTERS = {
    "min_stars": 100,  # Lowered default min stars for better yield
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
    ],
    "swift": [
        "language:swift stars:>1000 topic:swiftui",
        "language:swift stars:>500 topic:combine",
        "language:swift stars:>500 topic:swift-package-manager",
        "language:swift stars:>200", # Broad backup
        "language:swift SwiftUI examples", # Keyword backup
    ],
    "sql": [
        "language:sql stars:>100 license:mit",
        "topic:sql stars:>200 license:mit",
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
        "User-Agent": "TuminhAGI-Crawler/2.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        if e.code == 403:
            print(f"  ⚠️  Rate limit hit or Forbidden, waiting 60s...")
            time.sleep(60)
        elif e.code == 422: # Unprocessable Entity - often bad query
            print(f"  ⚠️  Bad query (422): {url}")
            return {}
        return {}
    except Exception as e:
        print(f"  ⚠️  Request error: {e}")
        return {}


def search_repos(query: str, token: str = None, per_page: int = 20) -> list:
    params = urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": per_page})
    url = f"https://api.github.com/search/repositories?{params}"
    data = github_request(url, token)
    return data.get("items", [])

def relax_query(query: str) -> str:
    """Tự động nới lỏng query để tìm được kết quả."""
    # 1. Nếu có stars:>N, giảm N mạnh hơn
    star_match = re.search(r'stars:>(\d+)', query)
    if star_match:
        stars = int(star_match.group(1))
        if stars > 100:
            new_stars = max(100, stars // 4)  # Giảm 4 lần
            return query.replace(f'stars:>{stars}', f'stars:>{new_stars}')
        else:
            # Xóa hẳn star filter
            return re.sub(r'stars:>\d+\s*', '', query).strip()
    
    # 2. Xóa bớt topic cuối cùng
    topics = re.findall(r'topic:[\w-]+', query)
    if topics:
        last_topic = topics[-1]
        return query.replace(last_topic, "").strip()
    
    # 3. Xóa các keyword khác trừ language
    parts = query.split()
    lang_parts = [p for p in parts if p.startswith("language:")]
    if len(parts) > len(lang_parts):
        return " ".join(lang_parts)
        
    return query

def search_repos_with_fallback(query: str, token: str = None) -> list:
    current_query = query
    max_attempts = 5
    for attempt in range(max_attempts):
        print(f"🔍 Searching: {current_query}")
        repos = search_repos(current_query, token)
        if repos:
            return repos
        
        if attempt < max_attempts - 1:
            next_query = relax_query(current_query)
            if next_query == current_query or not next_query:
                break
            current_query = next_query
            print(f"  ⚠️  No results. Relaxing query to: {current_query}")
            time.sleep(1)
        
    return []

# ─── UTILS ───────────────────────────────────────────────────────────────────

def get_repo_contents(owner: str, repo: str, path: str = "", token: str = None) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    data = github_request(url, token)
    if isinstance(data, list):
        return data
    return []


def get_file_content(download_url: str, token: str = None) -> str:
    try:
        headers = {"User-Agent": "TuminhAGI-Crawler/2.0"}
        if token:
            headers["Authorization"] = f"token {token}"
        req = Request(download_url, headers=headers)
        with urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

# ─── PARSERS ─────────────────────────────────────────────────────────────────

def extract_python_functions(code: str) -> list:
    functions = []
    try:
        tree = ast.parse(code)
    except Exception:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_") or node.name.startswith("test_"):
            continue
        docstring = ast.get_docstring(node)
        if not docstring or len(docstring.split()) < QUALITY_FILTERS["min_docstring_words"]:
            continue
        try:
            lines = code.split("\n")
            start = node.lineno - 1
            end = node.end_lineno
            func_lines = lines[start:end]
            if not (QUALITY_FILTERS["min_function_lines"] <= len(func_lines) <= QUALITY_FILTERS["max_function_lines"]):
                continue
            functions.append({"name": node.name, "code": "\n".join(func_lines), "docstring": docstring, "lines": len(func_lines)})
        except Exception:
            continue
    return functions

def extract_swift_functions(code: str) -> list:
    functions = []
    # Regex basic cho Swift func
    pattern = r'(///.*?\n)*\s*(public|private|internal|open)?\s*(func|class func|static func)\s+(\w+)[^{]*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
    for match in re.finditer(pattern, code, re.MULTILINE | re.DOTALL):
        comment, _, _, name, body = match.groups()
        if name.startswith("test") or name.startswith("_"): continue
        lines = match.group(0).split("\n")
        if not (QUALITY_FILTERS["min_function_lines"] <= len(lines) <= QUALITY_FILTERS["max_function_lines"]):
            continue
        doc = (comment or "").replace("///", "").strip()
        functions.append({"name": name, "code": match.group(0), "docstring": doc, "lines": len(lines)})
    return functions

# ─── CONVERTERS ─────────────────────────────────────────────────────────────

def to_example(func: dict, repo_name: str, lang: str) -> dict:
    if lang == "python":
        instruction = f"Giải thích và cải thiện hàm Python `{func['name']}`."
    else:
        instruction = f"Review và đề xuất cải thiện hàm Swift `{func['name']}`."
    
    return {
        "instruction": instruction,
        "input": func["code"],
        "output": f"Phân tích hàm `{func['name']}` từ repository `{repo_name}`:\n\nMục đích: {func['docstring']}\n\nĐề xuất: Tối ưu hóa logic, xử lý lỗi và thêm unit test.",
        "source": "github",
        "repo": repo_name
    }

# ─── CRAWLER ─────────────────────────────────────────────────────────────────

def crawl_repo(owner: str, repo: str, language: str, token: str = None) -> list:
    examples = []
    contents = get_repo_contents(owner, repo, "", token)
    ext = {"python": ".py", "swift": ".swift", "sql": ".sql", "javascript": ".js"}.get(language, ".py")

    files = [item for item in contents if item.get("type") == "file" and item.get("name", "").endswith(ext)]
    for file_item in files[:5]:
        content = get_file_content(file_item.get("download_url"), token)
        if not content or len(content) > 50000: continue
        
        funcs = []
        if language == "python": funcs = extract_python_functions(content)
        elif language == "swift": funcs = extract_swift_functions(content)
        
        for func in funcs[:3]:
            examples.append(to_example(func, f"{owner}/{repo}", language))
        time.sleep(0.5)
    return examples

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TuminhAGI GitHub Crawler v2")
    parser.add_argument("--language", required=True, choices=list(SEARCH_QUERIES.keys()))
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--query", default=None, help="Custom GitHub search query")
    parser.add_argument("--output-dir", default="finetune/datasets")
    parser.add_argument("--token", default=None)
    parser.add_argument("--worker", default="github_bot")
    args = parser.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🕷️  TuminhAGI GitHub Crawler v2")
    print(f"   Language: {args.language} | Target: {args.count} examples")
    
    # Load hashes to dedupe
    seen = set()
    for f in output_dir.glob("*.json"):
        if "summary" in f.name: continue
        try:
            data = json.load(open(f, encoding="utf-8"))
            for ex in data:
                h = hashlib.md5(ex.get("instruction", "").encode()).hexdigest()
                seen.add(h)
        except: pass
    print(f"   Existing: {len(seen)} instructions loaded.")

    all_examples = []
    queries = [args.query] if args.query else SEARCH_QUERIES[args.language]
    chunk = 1

    for q in queries:
        if len(all_examples) >= args.count: break
        
        repos = search_repos_with_fallback(q, token)
        print(f"   Found {len(repos)} repos")
        
        for repo in repos:
            if len(all_examples) >= args.count: break
            owner, name = repo["owner"]["login"], repo["name"]
            print(f"   📦 {owner}/{name} ", end="", flush=True)
            
            examples = crawl_repo(owner, name, args.language, token)
            new = []
            for ex in examples:
                h = hashlib.md5(ex.get("instruction", "").encode()).hexdigest()
                if h not in seen:
                    seen.add(h)
                    new.append(ex)
            
            all_examples.extend(new)
            print(f"-> +{len(new)} (Total: {len(all_examples)}/{args.count})")

            # Save chunks
            if len(all_examples) >= chunk * 20:
                sl = all_examples[(chunk-1)*20:chunk*20]
                fname = output_dir / f"{args.worker}_{args.language}_{chunk:03d}_{datetime.now().strftime('%H%M%S')}.json"
                json.dump(sl, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                print(f"  💾 Saved {fname.name}")
                chunk += 1
            time.sleep(1)

    # Save remainder
    rem = all_examples[(chunk-1)*20:]
    if rem:
        fname = output_dir / f"{args.worker}_{args.language}_{chunk:03d}_{datetime.now().strftime('%H%M%S')}.json"
        json.dump(rem, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  💾 Saved {fname.name}")

    print(f"\n✨ Xong! Đã thu hoạch {len(all_examples)} examples.")

if __name__ == "__main__":
    main()
