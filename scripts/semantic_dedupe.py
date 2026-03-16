import json
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    print("⚠️  Warning: sentence-transformers not found. Reverting to basic hashing.")
    SentenceTransformer = None

def semantic_dedupe():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="finetune/datasets")
    parser.add_argument("--output-file", default="finetune/datasets/FINAL_train_semantic.json")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    all_files = list(input_path.glob("*.json"))
    
    combined_data = []
    print(f"📂 Đang đọc {len(all_files)} files...")
    
    for f in all_files:
        if "summary" in f.name or "FINAL" in f.name:
            continue
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    combined_data.extend(data)
        except:
            pass

    print(f"📊 Tổng số examples thô: {len(combined_data)}")

    if not combined_data:
        return

    if SentenceTransformer is None:
        # Fallback to basic hashing
        seen = set()
        unique = []
        for ex in combined_data:
            key = ex.get("instruction", "").strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(ex)
        print(f"✨ Dedupe (basic) xong: {len(unique)} examples.")
    else:
        # Semantic Dedupe
        print(f"🧠 Bắt đầu Semantic Dedupe (Threshold: {args.threshold})...")
        model = SentenceTransformer(args.model)
        
        instructions = [ex.get("instruction", "") for ex in combined_data]
        embeddings = model.encode(instructions, show_progress_bar=True, convert_to_tensor=True)
        
        # Calculate similarity matrix
        cosine_scores = util.cos_sim(embeddings, embeddings)
        
        to_remove = set()
        for i in range(len(instructions)):
            if i in to_remove:
                continue
            for j in range(i + 1, len(instructions)):
                if cosine_scores[i][j] > args.threshold:
                    to_remove.add(j)
        
        unique = [combined_data[i] for i in range(len(combined_data)) if i not in to_remove]
        print(f"✨ Semantic Dedupe xong: Giữ lại {len(unique)}/{len(combined_data)} examples.")

    # Save
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"💾 Đã lưu vào {args.output_file}")

if __name__ == "__main__":
    semantic_dedupe()
