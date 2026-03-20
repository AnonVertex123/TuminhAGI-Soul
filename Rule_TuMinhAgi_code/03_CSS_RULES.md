# 03 — Luật CSS/UI — BẤT BIẾN

## Files TUYỆT ĐỐI không được sửa
frontend/app/globals.css           🔒 LOCKED
frontend/tailwind.config.ts        🔒 LOCKED
frontend/components/clickup/       🔒 LOCKED (toàn bộ folder)

## Color Tokens — dùng đúng ngữ nghĩa
```css
/* Layout */
--sidebar-bg:     #1B1B2F
--sidebar-active: #7B68EE
--main-bg:        #F8F8FC

/* Medical — KHÔNG dùng sai ngữ nghĩa */
--emergency:      #FF4444  /* CHỈ cho cấp cứu */
--herbal:         #22C55E  /* CHỈ cho thuốc Nam */
--western:        #3B82F6  /* CHỈ cho Tây y */
--warning:        #F59E0B  /* urgent cases */
```

## Khi thêm feature mới
✅ ĐÚNG:

Tạo components/[feature]/NewComponent.tsx
Dùng Tailwind classes trong file mới
Import vào page/panel như child component

❌ SAI:

Sửa globals.css
Sửa tailwind.config.ts
Sửa className trong clickup/*.tsx
Thêm <style> tag vào file cũ

## Responsive Rules
Desktop ≥1280px: 4 cột đầy đủ
Tablet 768-1280px: thu sidebar
Mobile <768px: bottom tabs + floating Minh Biên

## Sau mỗi task — PHẢI kiểm tra
```bash
git diff frontend/app/globals.css      # Phải trống
git diff frontend/tailwind.config.ts   # Phải trống
npm run build                          # Phải pass
```
---

