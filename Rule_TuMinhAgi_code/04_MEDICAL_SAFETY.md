# 04 — Luật An toàn Y tế — TỐI THƯỢNG

## 6 Safety Gates — KHÔNG BAO GIỜ BYPASS
Gate 0 — Emergency block
IF disease IN [I21,I63,G41,K92,O00,J96,I61,K35,G03]
THEN herbal_options = []
is_emergency = True
show_911_banner = True
NEVER remove this gate
Gate 1 — Pregnancy check
Runs BEFORE all other gates
Remove herbs with "thai kỳ" in contraindications
Add pregnancy_warning to output
NEVER skip for pregnant users
Gate 2 — Drug interaction
Flag: Đan sâm + warfarin
Flag: Cam thảo + digoxin
Flag: Hà thủ ô + statins
NEVER hide interaction warnings
Gate 3 — Constitution filter
PHONG_NHIET: exclude tinh="ôn/nhiệt"
PHONG_HAN:   exclude tinh="hàn/lương"
DUONG_HU:    exclude tinh="hàn"
AM_HU:       exclude tinh="táo"
Gate 4 — Evidence level
ALWAYS show evidence level
NEVER hide from user
high   → "Có nghiên cứu lâm sàng"
medium → "Kinh nghiệm dân gian"
low    → "Truyền thống — chưa có nghiên cứu"
Gate 5 — Language guard
FORBIDDEN words (auto-replace):
"bạn bị" → "có thể liên quan đến"
"chẩn đoán là" → "gợi ý tham khảo"
"điều trị bằng" → "hỗ trợ bằng"
"chắc chắn" → "có thể"

## Disclaimer — LUÔN HIỂN THỊ
"Thông tin tham khảo — không thay thế
chẩn đoán và điều trị của bác sĩ."

Phải xuất hiện ở CUỐI MỌI output y tế.
KHÔNG được ẩn, KHÔNG được xóa.

## Bệnh nhi — Luật riêng
< 1 tuổi:  KHÔNG gợi ý thuốc Nam
1-3 tuổi:  1/4 liều người lớn
3-6 tuổi:  1/3 liều người lớn
6-12 tuổi: 1/2 liều người lớn
TUYỆT ĐỐI CẤM cho trẻ em:

Phụ tử, Mã tiền
Hoàng liên (< 3 tuổi)
Đại hoàng liều cao

## Trước khi release tính năng y tế mới
□ Bác sĩ YHCT review data mới
□ 77/77 clinical tests vẫn PASS
□ Emergency gate test: ?emergency=1
□ Drug interaction test với warfarin
□ Pregnancy test với ca 42, 50
---

