# 🏛️ ĐẾ CHẾ ĐẠI MINH - NHẬT KÝ TIẾN HÓA TUMINHAGI
> "Tâm là gốc, Trí là hoa. Tiến hóa là quả." - Tự Minh

---

## 📅 CHECKPOINT: 2026-03-19 | VERSION: V9.2 (NAVIGATOR MODE)

### 🧠 1. THAY ĐỔI LOGIC CỐT LÕI (CORE EVOLUTION)
- **Dịch chuyển vai trò:** Từ "Bác sĩ chẩn đoán" sang "Hoa tiêu Y tế (Medical Navigator)".
- **Ngôn ngữ thiết quân luật:** Cấm tuyệt đối "Bạn bị...", "Chẩn đoán là...". Thay bằng ngôn ngữ gợi mở dựa trên Similarity.
- **Cơ chế Similarity Check:**
    - `0.33`: Ngưỡng nhạy bén cho Cấp cứu (Thai ngoài tử cung, Đột quỵ...).
    - `0.38`: Ngưỡng chuẩn cho các bệnh lý thông thường.
    - `< 0.38`: Tự động Reject nếu không phải ca cấp cứu.

### 🛡️ 2. BẢO TỒN DI SẢN (HERITAGE & DATA)
- **Nam Y Bách Khoa:** Tích hợp 800 vị thuốc Nam bồi bổ (Đinh lăng, Lạc tiên, Diệp hạ châu...).
- **Triết lý Hải Thượng Lãn Ông:** Đưa các câu châm ngôn y đức và phương pháp dưỡng sinh vào hệ thống.
- **Data Funnel:** Triệu chứng -> Chuẩn hóa (English Cross-check) -> Khóa Domain chuyên khoa -> Mã ICD tham khảo.

### 🛠️ 3. BÍ KÍP CODE "HỌC LÉN" TỪ CURSOR (STEALTH LEARNING)
- **Encoding Fix:** Sử dụng `[System.Uri]::EscapeDataString` trong PowerShell để gửi dữ liệu UTF-8 sạch.
- **Output Formatter:** Cấu trúc 4 Section (Tóm tắt - Khả năng - Nguy hiểm - Bản tin cho Bác sĩ).
- **Critic Gate:** Cách cài đặt Middleware để chặn đứng Hallucination (như lỗi "Trụy kinh").

### 🚀 4. ĐỊNH HƯỚNG LEVEL TIẾP THEO (NEXT LEVEL)
- [ ] Hoàn thiện Database 800 vị thuốc Nam (`jsonl`).
- [ ] Xây dựng UI Card màu xanh lá cho phần gợi ý Thảo dược.
- [ ] Tích hợp chỉ số sinh tồn (Vitals) và kết quả xét nghiệm (Labs).

---
*Ghi chú: File này là Trí nhớ Vĩnh cửu của TuminhAGI. Mọi Agent AI khi bắt đầu làm việc đều phải đọc file này trước.*
