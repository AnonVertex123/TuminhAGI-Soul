import json
import os
import re
from pathlib import Path

# --- CONFIG ---
DATASET_DIR = "finetune/datasets"
CATEGORIES = {
    "SwiftUI": [
        "View", "body", "HStack", "VStack", "ZStack", "padding", 
        "State", "Binding", "SwiftUI", "ForEach", "Spacer", "alignment"
    ],
    "Logic & Algorithm": [
        "func", "for", "if let", "guard", "map", "filter", "reduce", 
        "enum", "extension", "protocol", "switch", "return"
    ],
    "Architecture (MVVM/TCA)": [
        "ViewModel", "Store", "Reducer", "State", "Action", 
        "ObservableObject", "Published", "@Environment", "ComposableArchitecture"
    ],
    "Networking/API": [
        "URLSession", "Decodable", "async", "await", "Combine", 
        "Publisher", "JSONDecoder", "DataTask", "Task"
    ]
}

def analyze():
    dataset_path = Path(DATASET_DIR)
    json_files = list(dataset_path.glob("*.json"))
    
    total_count = 0
    cat_counts = {k: 0 for k in CATEGORIES}
    lengths = []
    unique_inputs = set()

    print(f"\n📊 Đang phân tích {len(json_files)} files trong {DATASET_DIR}...")

    for f in json_files:
        if "summary" in f.name: continue
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                for item in data:
                    total_count += 1
                    input_text = item.get("input", "")
                    lengths.append(len(input_text))
                    unique_inputs.add(input_text)
                    
                    found_any = False
                    for cat, keywords in CATEGORIES.items():
                        if any(k.lower() in input_text.lower() for k in keywords):
                            cat_counts[cat] += 1
                            found_any = True
        except Exception as e:
            print(f"  ⚠️  Lỗi khi đọc {f.name}: {e}")

    avg_len = sum(lengths) / len(lengths) if lengths else 0
    unique_count = len(unique_inputs)

    # In báo cáo
    print("\n" + "="*60)
    print(f"{'BÁO CÁO PHÂN TÍCH TUMINH-AGI DATASET':^60}")
    print("="*60)
    print(f" Tổng số ví dụ:          {total_count:,}")
    print(f" Ví dụ duy nhất:        {unique_count:,}")
    print(f" Tỷ lệ trùng lặp:       {((total_count-unique_count)/total_count*100):.2f}%" if total_count else "0%")
    print(f" Độ dài trung bình:     {avg_len:.0f} ký tự")
    print("-" * 60)
    print(f"{'HẠNG MỤC':<30} | {'SỐ LƯỢNG':<10} | {'TỶ LỆ':<10}")
    print("-" * 60)
    
    for cat, count in cat_counts.items():
        percent = (count / total_count * 100) if total_count else 0
        print(f"{cat:<30} | {count:<10} | {percent:>6.1f}%")
    
    print("-" * 60)
    
    # Đánh giá sơ bộ
    print("\n💡 ĐÁNH GIÁ ĐỘ SÂU:")
    if avg_len > 800:
        print("   ✅ Dữ liệu sâu: Các ví dụ có độ phức tạp cao, tốt cho fine-tuning.")
    elif avg_len > 300:
        print("   ⚠️  Dữ liệu trung bình: Cần bổ sung thêm code blocks dài hơn.")
    else:
        print("   ❌ Dữ liệu mỏng: Code quá ngắn, mô hình sẽ khó học được logic phức tạp.")

    print("\n✨ Hoàn tất báo cáo.")

if __name__ == "__main__":
    analyze()
