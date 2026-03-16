# I:\TuminhAgi\finetune\generate_expert_dataset.py
import json
import os
import sys
import time
from pathlib import Path
import ollama

# Cấu hình đường dẫn
BASE_DIR = Path("I:/TuminhAgi")
STORAGE_DIR = BASE_DIR / "storage"
DATASET_DIR = STORAGE_DIR / "expert_datasets"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

MODEL_GEN = "deepseek-r1:7b" # Hoặc model mạnh nhất bạn có

# Các chủ đề chuyên gia về Python & Logic
EXPERT_TOPICS = [
    "Concurrency & Parallelism (Multiprocessing, Asyncio, Threading) trong Python",
    "Design Patterns (Creational, Structural, Behavioral) áp dụng vào hệ thống phân tán",
    "Memory Management & Optimization (Garbage Collection, Slots, Generators)",
    "Hệ thống Logic: Khả năng tự sửa lỗi (Self-healing systems) và Circuit Breaker",
    "Security: Ngăn chặn SQL Injection, XSS và khai thác Buffer Overflow qua Python",
    "Kiến trúc Microservices: Communication (gRPC vs REST), Load Balancing",
    "Algorithms: Cấu trúc dữ liệu tùy chỉnh cho xử lý Big Data (Bloom Filters, Tries)"
]

def generate_batch(batch_id, samples_per_batch=20):
    new_samples = []
    topic = EXPERT_TOPICS[batch_id % len(EXPERT_TOPICS)]
    
    prompt = f"""
    Bạn là một Siêu Coder và Kiến trúc sư hệ thống. Hãy tạo {samples_per_batch} mẫu dữ liệu Alpaca format.
    CHỦ ĐỀ: {topic}
    
    YÊU CẦU CỨNG:
    1. Instruction: Đưa ra một bài toán lập trình hoặc một nút thắt logic hệ thống cực khó.
    2. Output: Bắt buộc theo format:
       <think>
       [Phân tích kiến trúc, xem xét các edge cases, so sánh các giải pháp, áp dụng triết lý Tự Minh: 'Hiểu bản chất để suy diễn']
       </think>
       [Code Python sạch, tối ưu, có type hints và giải thích logic sát thủ]
    3. Ngôn ngữ: Tiếng Việt.
    """

    try:
        response = ollama.chat(model=MODEL_GEN, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content']
        
        # Giả định model trả về danh sách, ta sẽ bóc tách sơ bộ (có thể cần regex tinh chỉnh hơn)
        # Ở đây ta lưu trực tiếp để Hùng Đại hậu xử lý
        sample = {
            "batch_id": batch_id,
            "topic": topic,
            "data": content
        }
        return sample
    except Exception as e:
        print(f"❌ Lỗi batch {batch_id}: {e}")
        return None

def main():
    total_batches = 500 # 500 batch x 20 mẫu = 10.000 mẫu
    print(f"🚀 Bắt đầu chiến dịch 10.000 mẫu sát thủ...")
    
    for i in range(total_batches):
        print(f"📦 Đang xử lý Batch {i+1}/{total_batches}...")
        batch_data = generate_batch(i)
        
        if batch_data:
            file_name = DATASET_DIR / f"batch_expert_{i+1:03d}.json"
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=4, ensure_ascii=False)
            print(f"✅ Đã lưu {file_name}")
        
        # Nghỉ ngắn để GPU hạ nhiệt
        time.sleep(2)

if __name__ == "__main__":
    main()