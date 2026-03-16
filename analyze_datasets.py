import os
import json
from collections import defaultdict

def analyze_datasets(directory):
    stats = defaultdict(lambda: {'file_count': 0, 'example_count': 0})
    
    for filename in os.listdir(directory):
        if filename.endswith('.json') and not filename.endswith('_summary.json'):
            path = os.path.join(directory, filename)
            
            # Determine category from filename
            # Example: hung_sql_001_055113.json -> hung_sql
            parts = filename.split('_')
            if len(parts) >= 2:
                category = '_'.join(parts[:2])
            else:
                category = 'other'
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        count = len(data)
                    else:
                        # Fallback for different structures if they exist
                        count = 1 if data else 0
                    
                    stats[category]['file_count'] += 1
                    stats[category]['example_count'] += count
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                
    return stats

if __name__ == "__main__":
    dataset_dir = r"i:\TuminhAgi\finetune\datasets"
    results = analyze_datasets(dataset_dir)
    
    print("| Category | File Count | Total Examples |")
    print("| :--- | :--- | :--- |")
    for category, data in sorted(results.items()):
        print(f"| {category} | {data['file_count']} | {data['example_count']} |")
