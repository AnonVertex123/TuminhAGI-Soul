from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


INPUT_PATH = Path("data/generated/generated.json")
OUTPUT_DIR = Path("data/filtered")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


MEDICAL_KEYWORDS = [
    "triệu chứng",
    "chẩn đoán",
    "điều trị",
    "thuốc",
    "bệnh",
    "sốt",
    "đau",
    "ho",
    "y tế",
    "bác sĩ",
    "dược liệu",
    "thuốc nam",
    "đông y",
    "hàn",
    "nhiệt",
    "hư",
    "thực",
    "symptom",
    "diagnosis",
    "treatment",
    "medicine",
    "clinical",
    "drug",
    "herbal",
    "patient",
    "medical",
]

SAFETY_BLACKLIST = [
    "tự tử",
    "tự làm hại",
    "overdose",
    "liều chết",
    "hack",
    "exploit",
    "malware",
    "virus",
]


def content_hash(sample: Dict[str, Any]) -> str:
    text = (sample.get("instruction") or "") + (sample.get("output") or "")
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_medical_relevant(sample: Dict[str, Any]) -> bool:
    text = (
        (sample.get("instruction") or "")
        + (sample.get("input") or "")
        + (sample.get("output") or "")
    ).lower()
    return any(kw in text for kw in MEDICAL_KEYWORDS)


def is_safe(sample: Dict[str, Any]) -> bool:
    text = ((sample.get("instruction") or "") + (sample.get("output") or "")).lower()
    return not any(kw in text for kw in SAFETY_BLACKLIST)


def is_quality(sample: Dict[str, Any]) -> bool:
    quality = float(sample.get("quality", 0.0) or 0.0)
    if quality < 0.6:
        return False

    instruction = sample.get("instruction") or ""
    output = sample.get("output") or ""
    if len(str(instruction)) < 10 or len(str(output)) < 20:
        return False

    return True


def filter_and_dedup() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(f"Missing input: {INPUT_PATH}")

    samples: List[Dict[str, Any]] = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise SystemExit("generated.json must be a list")

    print(f"[Filter] Input: {len(samples)} samples")

    safe = [s for s in samples if is_safe(s)]
    print(f"[Filter] After safety: {len(safe)}")

    quality = [s for s in safe if is_quality(s)]
    print(f"[Filter] After quality: {len(quality)}")

    medical = [s for s in quality if is_medical_relevant(s)]
    other = [s for s in quality if not is_medical_relevant(s)]
    print(f"[Filter] Medical: {len(medical)}, Other: {len(other)}")

    max_other = len(medical) // 4
    combined = medical + other[:max_other]

    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for s in combined:
        h = content_hash(s)
        if h in seen:
            continue
        seen.add(h)
        deduped.append(s)

    print(f"[Filter] After dedup: {len(deduped)}")

    alpaca_format: List[Dict[str, str]] = []
    for s in deduped:
        alpaca_format.append(
            {
                "instruction": str(s.get("instruction") or ""),
                "input": str(s.get("input") or ""),
                "output": str(s.get("output") or ""),
            }
        )

    output_path = OUTPUT_DIR / "dataset_alpaca.json"
    output_path.write_text(
        json.dumps(alpaca_format, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    stats = {
        "total_input": len(samples),
        "after_safety": len(safe),
        "after_quality": len(quality),
        "medical_relevant": len(medical),
        "final": len(deduped),
        "medical_ratio": round(len(medical) / len(deduped), 3) if deduped else 0,
    }
    (OUTPUT_DIR / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[Filter] Done — {len(deduped)} samples saved")
    print(f"[Stats] {stats}")


if __name__ == "__main__":
    filter_and_dedup()

