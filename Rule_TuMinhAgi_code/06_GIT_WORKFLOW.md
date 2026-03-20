# 06 — Git Workflow

## Commit Format
type(scope): mô tả ngắn gọn
Types:
feat     — tính năng mới
fix      — sửa lỗi
style    — CSS/UI (không logic)
refactor — tái cấu trúc
docs     — tài liệu
test     — thêm/sửa test
chore    — việc lặt vặt
medical  — thay đổi liên quan y tế
Scopes:
frontend, backend, pipeline,
emergency, medical, herbs, ui
Ví dụ:
feat(emergency): add hospital map with OSM
fix(gate0): ensure herbal empty on emergency
medical(herbs): add 50 new herb entries
style(sidebar): fix icon alignment

## Branches
main          ← production, luôn stable
develop       ← development branch
feature/xxx   ← tính năng mới
fix/xxx       ← bug fixes
medical/xxx   ← thay đổi data y tế

## Trước khi commit
```bash
□ npm run build          # PHẢI pass
□ python -m pytest tests/ # PHẢI 77/77 pass
□ git diff globals.css   # PHẢI trống
□ git diff tailwind.config.ts # PHẢI trống
```

## Files KHÔNG BAO GIỜ commit
.env
api_keys.txt
storage/chroma_db/
*.gguf *.bin *.safetensors
TUMINH_BRAIN.jsonl (private repo only)
node_modules/
.venv/
---

