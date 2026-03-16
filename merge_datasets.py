import os
import json
import hashlib
import random

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def merge_datasets(directory, output_file):
    prefixes = ['hung_python', 'github_python', 'hung_sql', 'hung_architecture', 'hung_philosophy']
    all_examples = []
    seen_hashes = set()
    stats = {p: 0 for p in prefixes}
    stats['total_raw'] = 0
    stats['duplicates'] = 0
    stats['invalid'] = 0
    
    print(f"Scanning directory: {directory}")
    
    for filename in os.listdir(directory):
        if not filename.endswith('.json') or filename.endswith('_summary.json'):
            continue
            
        matched_prefix = next((p for p in prefixes if filename.startswith(p)), None)
        if not matched_prefix:
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
                        
                    # Deduplication (using SHA-256 on input field, or instruction+input if input is often empty)
                    # Requirement says 'input' field, but let's be safe and use both if needed.
                    # Following literal requirement: input field hash.
                    input_hash = get_hash(input_text if input_text else instruction)
                    
                    if input_hash in seen_hashes:
                        stats['duplicates'] += 1
                        continue
                    
                    seen_hashes.add(input_hash)
                    all_examples.append(item)
                    stats[matched_prefix] += 1
                    
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    # Shuffle
    print(f"Merging {len(all_examples)} unique examples...")
    random.seed(42)
    random.shuffle(all_examples)
    
    # Export to JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in all_examples:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
    print("\n--- Merge Summary ---")
    print(f"Total Raw Examples: {stats['total_raw']}")
    print(f"Duplicates Removed: {stats['duplicates']}")
    print(f"Invalid Examples Skipped: {stats['invalid']}")
    print(f"Total Unique Examples: {len(all_examples)}")
    print("\nBreakdown by Category:")
    for p in prefixes:
        print(f"- {p}: {stats[p]}")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    dataset_dir = r"i:\TuminhAgi\finetune\datasets"
    output_path = os.path.join(dataset_dir, "tuminh_agi_v1_train.jsonl")
    merge_datasets(dataset_dir, output_path)
