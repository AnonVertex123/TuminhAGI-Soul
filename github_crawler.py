"""
TuminhAGI — GitHub Crawler v2.5 (Turbo Hunter Edition)
Crawl code thật từ GitHub public repos → convert thành training examples.

Tính năng mới:
  - Turbo Search: Dùng Git Trees API (recursive=1) lấy toàn bộ file trong 1 request.
  - Siêu đa luồng: 15 workers chạy song song.
  - Junk Filter: Bỏ qua Tests, Pods, build, node_modules...
  - Raw Access: Tải code từ raw.githubusercontent.com để né rate limit.
"""

import os
import sys
import json
import time
import argparse
import ast
import re
import hashlib
import requests
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ─── WINDOWS FIX ─────────────────────────────────────────────────────────────
if sys.platform == "win32":
    if "PYTHONHOME" not in os.environ:
        os.environ["PYTHONHOME"] = sys.prefix
    if "PYTHONPATH" not in os.environ:
        os.environ["PYTHONPATH"] = os.path.join(sys.prefix, "Lib")

# ─── CONFIG ──────────────────────────────────────────────────────────────────

QUALITY_FILTERS = {
    "min_stars": 50,
    "min_function_lines": 20,   # Hạ từ 40 xuống 20 để "vào việc" nhanh hơn
    "max_function_lines": 500, 
    "min_docstring_words": 0,    # SwiftUI thường ít docstring, ta không nên ép buộc
}

SEARCH_QUERIES = {
    "python": [
        "language:python stars:200..1000",
        "language:python topic:fastapi",
        "language:python topic:machine-learning",
    ],
    "swift": [
        "language:swift stars:100..500",      # Tìm những viên ngọc thô tâm huyết
        "language:swift \"struct *: View\"", # Bắt buộc phải có cấu trúc View (SwiftUI)
        "language:swift \"async throws\"",   # Code xử lý API hiện đại
        "language:swift topic:combine",
        "language:swift topic:swiftui",
    ],
}

JUNK_PATHS = ["test", "pod", "build", "node_modules", "carthage", "documentation", "example"]

# ─── GLOBAL STATE (THREAD-SAFE) ──────────────────────────────────────────────
lock = threading.Lock()
seen_hashes = set()
total_collected = 0
progress_chunk = 1

# ─── GITHUB API ──────────────────────────────────────────────────────────────

def github_request(url: str, token: str = None, params: dict = None) -> dict:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TuminhAGI-Turbo-Hunter-v2.5",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code != 200:
            print(f"❌ Lỗi GitHub API ({response.status_code}): {response.text}")
            
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            # Rate limit handling
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait_time = max(10, reset_time - int(time.time()))
            print(f"  ⚠️  Rate limit, waiting {wait_time}s...")
            time.sleep(wait_time)
        return {}
    except Exception: return {}

def search_repos(query: str, token: str = None, per_page: int = 15) -> list:
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    headers = {
        "Authorization": f"token {token}" if token else None,
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TuminhAGI-Turbo-Hunter-v2.5"
    }
    if not token: headers.pop("Authorization")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code != 200:
            print(f"❌ Lỗi GitHub API ({response.status_code}): {response.text}")

        if response.status_code == 200:
            data = response.json()
            return data.get("items", [])
        return []
    except Exception: return []

def relax_query(query: str) -> str:
    # 1. Xử lý dải stars: 100..500 -> 50..500 -> 30..500
    range_match = re.search(r'stars:(\d+)\.\.(\d+)', query)
    if range_match:
        low, high = int(range_match.group(1)), int(range_match.group(2))
        new_low = max(30, low // 2)
        if new_low == low: return re.sub(r'stars:\d+\.\.\d+\s*', '', query).strip()
        return query.replace(f'stars:{low}..{high}', f'stars:{new_low}..{high}')
    
    # 2. Xử lý stars đơn: stars:>200
    star_match = re.search(r'stars:>(\d+)', query)
    if star_match:
        stars = int(star_match.group(1))
        new_stars = max(30, stars // 4)
        if new_stars == stars: return re.sub(r'stars:>\d+\s*', '', query).strip()
        return query.replace(f'stars:>{stars}', f'stars:>{new_stars}')
    return query

def search_repos_with_fallback(query: str, token: str = None) -> list:
    current_query = query
    for _ in range(3):
        repos = search_repos(current_query, token)
        if repos: return repos
        current_query = relax_query(current_query)
        time.sleep(1)
    return []

# ─── TURBO CRAWL LOGIC ───────────────────────────────────────────────────────

def crawl_repo_turbo(owner: str, name: str, lang: str, branch: str = "main", token: str = None) -> list:
    repo_full = f"{owner}/{name}"
    all_examples = []
    ext = ".py" if lang == "python" else ".swift"
    
    # Dùng Git Trees API với recursive=1 và đúng branch mặc định
    tree_url = f"https://api.github.com/repos/{repo_full}/git/trees/{branch}?recursive=1"
    data = github_request(tree_url, token)
    
    if not data or "tree" not in data:
        # Thử lại với master nếu branch truyền vào thất bại (phòng hờ)
        if branch != "master":
            tree_url = tree_url.replace(f"/{branch}?", "/master?")
            data = github_request(tree_url, token)
        
        if not data or "tree" not in data:
            return []

    # Lọc file code xịn
    candidate_files = []
    for item in data["tree"]:
        if item["type"] == "blob" and item["name"].lower().endswith(ext):
            path_lower = item["path"].lower()
            # Junk Filter nâng cao: Bỏ Tests, Mock, Package.swift
            if any(junk in path_lower for junk in JUNK_PATHS): continue
            if "test" in path_lower or "mock" in path_lower: continue
            if path_lower.endswith("package.swift"): continue
            
            candidate_files.append(item["path"])

    if not candidate_files:
        print(f"   ⚠️  {repo_full}: 0 files matches {ext} (filtered)")
        return []

    # Giới hạn lấy 10 file tinh hoa nhất mỗi repo để tránh spam
    for path in candidate_files[:10]:
        raw_url = f"https://raw.githubusercontent.com/{repo_full}/{branch}/{path}"
        try:
            resp = requests.get(raw_url, timeout=10)
            if resp.status_code == 200:
                code = resp.text
                funcs = extract_python(code) if lang == "python" else extract_swift(code)
                for f in funcs:
                    all_examples.append(to_example(f, repo_full, lang))
            else:
                print(f"      ❌ Raw Error ({resp.status_code}): {raw_url}")
        except Exception as e:
            print(f"      ❌ Raw Exception: {e}")
        
    return all_examples

def extract_python(code: str) -> list:
    funcs = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"): continue
                doc = ast.get_docstring(node) or "Description."
                lines = code.splitlines()[node.lineno-1:node.end_lineno]
                if QUALITY_FILTERS["min_function_lines"] <= len(lines) <= QUALITY_FILTERS["max_function_lines"]:
                    funcs.append({"name": node.name, "code": "\n".join(lines), "docstring": doc})
    except: pass
    return funcs

def extract_swift(code: str) -> list:
    funcs = []
    lines = code.splitlines()
    pattern = r'^\s*(///.*?\n)*\s*(public|private|internal|open)?\s*(func|struct|class|enum|extension|protocol)\s+(\w+)'
    
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            chunk, doc = [], []
            j = i - 1
            while j >= 0 and lines[j].strip().startswith("///"):
                doc.insert(0, lines[j].replace("///", "").strip())
                j -= 1
            
            start_i = i
            end_i = min(len(lines), i + 100)
            brace_count, found_open = 0, False
            for k in range(start_i, end_i):
                chunk.append(lines[k])
                brace_count += lines[k].count("{")
                brace_count -= lines[k].count("}")
                if "{" in lines[k]: found_open = True
                if found_open and brace_count <= 0:
                    break
            
            if QUALITY_FILTERS["min_function_lines"] <= len(chunk) <= QUALITY_FILTERS["max_function_lines"]:
                name_match = re.search(r'(func|struct|class|enum|extension|protocol)\s+(\w+)', line)
                name = name_match.group(2) if name_match else "unknown"
                funcs.append({
                    "name": name, 
                    "code": "\n".join(chunk), 
                    "docstring": " ".join(doc) if doc else "Swift production example."
                })
            else:
                # Debug ranh mãnh: in ra nếu file bị loại vì quá ngắn
                if len(chunk) > 0:
                    pass # print(f"      ⚠️  Bỏ qua {line.strip()[:20]}... (Chỉ có {len(chunk)} dòng)")
    return funcs

def to_example(func: dict, repo: str, lang: str) -> dict:
    return {
        "instruction": f"Giải thích và phân tích đoạn code {lang} sau: `{func['name']}`",
        "input": func["code"],
        "output": f"Đây là đoạn code trích từ repository `{repo}`.\n\nChức năng: {func['docstring']}\n\nPhân tích: Code chuẩn, xử lý tốt.",
        "repo": repo
    }

# ─── THREADING MANAGER ───────────────────────────────────────────────────────

def process_repo(repo, lang, token, output_dir, target_count, worker_name):
    global total_collected, progress_chunk
    
    with lock:
        if total_collected >= target_count: return

    owner, name = repo["owner"]["login"], repo["name"]
    branch = repo.get("default_branch", "main")
    
    print(f"   🔍 Cào repo: {owner}/{name} (Branch: {branch})")
    examples = crawl_repo_turbo(owner, name, lang, branch, token)
    
    new_found = []
    with lock:
        for ex in examples:
            if total_collected >= target_count: break
            h = hashlib.md5(ex["input"].encode()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h); seen_hashes.add(h) # Dùng input hash đẻ tránh trùng
                new_found.append(ex)
                total_collected += 1
        
        if new_found:
            print(f"   ✅ {owner}/{name}: +{len(new_found)} (Total: {total_collected}/{target_count})")
            if total_collected // 20 >= progress_chunk:
                fname = output_dir / f"{worker_name}_{lang}_{progress_chunk:03d}.json"
                json.dump(new_found, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                progress_chunk += 1
            else:
                fname = output_dir / f"temp_{worker_name}_{lang}.json"
                json.dump(new_found, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--token")
    parser.add_argument("--worker", default="turbo_bot")
    # THÊM DÒNG NÀY ĐỂ MỞ ỐNG NGẮM SÁT THỦ
    parser.add_argument("--query", help="Custom search query to override defaults")
    args = parser.parse_args()

    token = (args.token or os.getenv("GITHUB_TOKEN", "")).strip()
    output_dir = Path("finetune/datasets")
    output_dir.mkdir(parents=True, exist_ok=True)

    for f in output_dir.glob("*.json"):
        try:
            d = json.load(open(f, encoding="utf-8"))
            for ex in d: seen_hashes.add(hashlib.md5(ex["input"].encode()).hexdigest())
        except: pass

    print(f"\n🕷️  TuminhAGI Turbo Hunter v2.8 [FULL VISION]")
    print(f"   Target: {args.count} | Existing: {len(seen_hashes)}")

    # LOGIC CHỌN MỤC TIÊU
    if args.query:
        queries = [args.query]
        print(f"🎯 Sử dụng Query tùy chỉnh: {args.query}")
    else:
        queries = SEARCH_QUERIES.get(args.language, [f"language:{args.language} stars:>100"])
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        for q in queries:
            if total_collected >= args.count: break
            repos = search_repos_with_fallback(q, token)
            for repo in repos:
                executor.submit(process_repo, repo, args.language, token, output_dir, args.count, args.worker)

    print(f"\n✨ Xong! Đã thu hoạch thêm {total_collected} examples.")

if __name__ == "__main__":
    main()
