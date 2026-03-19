import sys
import io
import requests
import json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def check_clinical_reasoning():
    # Giả lập ca bệnh: Viêm màng não (Meningitis)
    # Triệu chứng: Sốt cao + Đau đầu + Cứng cổ + Sợ ánh sáng
    query = "Bệnh nhân sốt cao, đau đầu dữ dội, nôn mửa, có dấu hiệu sợ ánh sáng và cứng cổ"
    
    url = "http://localhost:8000/diagnose/stream"
    params = {"query": query}
    
    print(f"🚀 Đang gửi ca lâm sàng 'Hắc ám' tới Tự Minh V9.1...")
    print(f"📝 Query: {query}\n")
    print("-" * 50)

    try:
        # Gọi API với chế độ stream (SSE)
        with requests.get(url, params=params, stream=True, timeout=10) as response:
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        content = decoded_line[6:] # Bỏ tiền tố 'data: '
                        try:
                            data = json.loads(content)
                            
                            # Kiểm tra xem có Red Flags hay Expert Insights không
                            if "red_flags" in data and data["red_flags"]:
                                print(f"🚨 [RED FLAG DETECTED]: {data['red_flags']}")
                            
                            if "expert_insights" in data:
                                print(f"🧠 [EXPERT REASONING]: {data['expert_insights']}")
                                
                            if "diagnoses" in data:
                                print(f"📊 [TOP DIAGNOSES]:")
                                for d in data["diagnoses"][:3]: # Lấy Top-3
                                    print(f"   - {d['name']} ({d['probability']*100:.1f}%)")
                                    
                        except json.JSONDecodeError:
                            # In các đoạn text stream thông thường (Typewriter effect)
                            print(content, end="", flush=True)

    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")

if __name__ == "__main__":
    check_clinical_reasoning()