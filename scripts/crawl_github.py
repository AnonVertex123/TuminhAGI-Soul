from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import requests


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
if not GITHUB_TOKEN:
    raise SystemExit(
        "Missing env `GITHUB_TOKEN`. Set it in GitHub Actions secrets."
    )

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

CONFIG_PATH = Path("config/crawl_config.json")
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def search_repos(topic: str) -> List[Dict[str, Any]]:
    url = "https://api.github.com/search/repositories"
    params = {
        "q": f"topic:{topic} language:Python stars:>{CONFIG['min_stars']}",
        "sort": "stars",
        "per_page": CONFIG["max_repos_per_topic"],
    }
    res = requests.get(url, headers=HEADERS, params=params, timeout=30)
    res.raise_for_status()
    return res.json().get("items", [])


def get_repo_files(repo_full_name: str) -> List[str]:
    url = f"https://api.github.com/repos/{repo_full_name}/git/trees/HEAD"
    params = {"recursive": "1"}
    res = requests.get(url, headers=HEADERS, params=params, timeout=60)
    if res.status_code != 200:
        return []

    tree = res.json().get("tree", [])
    files: List[str] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path = item.get("path") or ""
        size_kb = float(item.get("size", 0) or 0) / 1024.0

        if not any(path.endswith(ext) for ext in CONFIG["file_extensions"]):
            continue
        if any(ex in path.lower() for ex in CONFIG["exclude_paths"]):
            continue
        if size_kb > float(CONFIG["max_file_size_kb"]):
            continue

        files.append(path)

    return files[: int(CONFIG["max_files_per_repo"])]


def download_file(repo_full_name: str, path: str) -> str | None:
    url = f"https://raw.githubusercontent.com/{repo_full_name}/HEAD/{path}"
    res = requests.get(url, headers=HEADERS, timeout=60)
    if res.status_code == 200:
        return res.text
    return None


def crawl() -> None:
    all_samples: List[Dict[str, Any]] = []
    seen_repos: set[str] = set()

    for topic in CONFIG["topics"]:
        print(f"[Crawl] Topic: {topic}")
        repos = search_repos(topic)

        for repo in repos:
            full_name = repo.get("full_name")
            if not full_name or full_name in seen_repos:
                continue
            seen_repos.add(full_name)

            print(f"  Repo: {full_name} ⭐{repo.get('stargazers_count', 0)}")
            files = get_repo_files(full_name)

            for file_path in files:
                content = download_file(full_name, file_path)
                if not content or len(content.strip()) < 100:
                    continue

                all_samples.append(
                    {
                        "repo": full_name,
                        "path": file_path,
                        "content": content,
                        "stars": repo.get("stargazers_count", 0),
                        "topic": topic,
                    }
                )

                time.sleep(0.5)  # Rate limit

    output_path = OUTPUT_DIR / "crawled.json"
    output_path.write_text(
        json.dumps(all_samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[Crawl] Done — {len(all_samples)} files saved to {output_path}")


if __name__ == "__main__":
    crawl()

