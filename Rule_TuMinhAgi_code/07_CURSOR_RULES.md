# 07 — Luật riêng cho Cursor AI

## Trước khi bắt đầu MỌI task

Đọc Rule_TuMinhAgi_code/ folder
Liệt kê files sẽ THAY ĐỔI
Liệt kê files sẽ TẠO MỚI
Confirm không đụng PROTECTED files
Chỉ bắt đầu sau khi confirm xong


## PROTECTED FILES — không bao giờ sửa
frontend/app/globals.css
frontend/tailwind.config.ts
frontend/components/clickup/*.tsx
nexus_core/armored_critic.py
nexus_core/strict_validator.py
nexus_core/professor_reasoning.py
soul_vault/
memory/

## Pattern thêm feature mới
✅ LUÔN LÀM:

Tạo file/component MỚI
Import vào đúng vị trí
Thêm types/interfaces
Thêm error handling
Thêm offline fallback

❌ KHÔNG BAO GIỜ:

Sửa globals.css
Sửa existing className
Xóa safety gates
Bypass emergency check
Dùng 'any' trong TypeScript

## Sau khi hoàn thành task
```bash
# Cursor phải tự chạy:
git diff frontend/app/globals.css
git diff frontend/tailwind.config.ts
npm run build
# Báo cáo kết quả trước khi xong
```

## Nếu task conflict với luật
Cursor phải:

Dừng lại
Báo conflict cụ thể
Đề xuất cách làm không vi phạm luật
Chờ confirm từ owner trước khi tiếp tục

---

