import json
import hashlib
from pathlib import Path
from collections import defaultdict

def main():
    datasets_dir = Path('finetune/datasets')
    all_ex = []
    topics = defaultdict(int)

    for f in sorted(datasets_dir.glob('*.json')):
        if 'summary' in f.name or 'FINAL' in f.name:
            continue
        try:
            with open(f, encoding='utf-8') as fp:
                data = json.load(fp)
            if isinstance(data, list):
                for ex in data:
                    ex['_topic'] = f.name.split('_')[1] if '_' in f.name else 'unknown'
                all_ex.extend(data)
        except Exception:
            pass

    seen = set()
    unique = []
    for ex in all_ex:
        h = hashlib.md5(ex.get('instruction', '').strip().lower().encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(ex)
            topics[ex['_topic']] += 1

    print('=== TIẾN ĐỘ HIỆN TẠI ===')
    for t, c in sorted(topics.items()):
        bar = '█' * (c // 10)
        print(f'  {t:15} {c:4}  {bar}')
    print('  ' + '─' * 40)
    print(f'  Unique tổng: {len(unique)}')
    status = '✅ RỒI!' if len(unique) >= 500 else f'cần thêm {500 - len(unique)}'
    print(f'  Train được:  {status}')

if __name__ == '__main__':
    main()
