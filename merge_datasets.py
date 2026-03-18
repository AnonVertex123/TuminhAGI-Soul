import os
import json
import hashlib
import random

def get_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def merge_datasets(directory, output_file):
    all_examples = []
    seen_hashes = set()
    stats = {
        'total_raw': 0,
        'duplicates': 0,
        'invalid': 0,
    }
    
    print(f"🚀 Scanning directory: {directory}")
    
    for filename in os.listdir(directory):
        # Chỉ lấy file .json, bỏ qua các file summary
        if not filename.endswith('.json') or '_summary.json' in filename:
            continue
            
        path = os.path.join(directory, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                
                for item in data:
                    stats['total_raw'] += 1
                    
                    # Validation
                    instruction = item.get('instruction', '').strip()
                    input_text = item.get('input', '').strip()
                    output_text = item.get('output', '').strip()
                    
                    if not instruction or not output_text:
                        stats['invalid'] += 1
                        continue
                        
                    # Deduplication dựa trên hash của 'input' (code contents)
                    input_hash = get_hash(input_text)
                    
                    if input_hash in seen_hashes:
                        stats['duplicates'] += 1
                        continue
                    
                    seen_hashes.add(input_hash)
                    all_examples.append(item)
                    
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    # Shuffle để dữ liệu được phân phối đều
    print(f"🔄 Merging {len(all_examples)} unique examples...")
    random.seed(42)
    random.shuffle(all_examples)
    
    # Export to JSONL (đúng format train finetuning)
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in all_examples:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
    print("\n========================================")
    print("      BÁO CÁO GỘP DATASET TUMINH-AGI    ")
    print("========================================")
    print(f" Total Raw Examples:   {stats['total_raw']:,}")
    print(f" Duplicates Removed:   {stats['duplicates']:,}")
    print(f" Invalid Skipped:      {stats['invalid']:,}")
    print(f" FINAL UNIQUE TOTAL:   {len(all_examples):,}")
    print("----------------------------------------")
    print(f" Output: {output_file}")
    print("========================================\n")

if __name__ == "__main__":
    dataset_dir = r"i:\TuminhAgi\finetune\datasets"
    output_path = os.path.join(dataset_dir, "tuminh_swift_v1_final.jsonl")
    merge_datasets(dataset_dir, output_path)
