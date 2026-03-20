# 05 — Tiêu chuẩn Code

## Python
```python
# ✅ ĐÚNG
async def diagnose(ctx: SymptomContext) -> DiagnosisResult:
    """
    Chẩn đoán triệu chứng và trả về kết quả.
    
    Args:
        ctx: SymptomContext với triệu chứng và ngữ cảnh
    Returns:
        DiagnosisResult với top candidates và treatment
    """
    pass

# ❌ SAI — không có type hints, không docstring
def diagnose(symptoms):
    pass
```

### Rules Python:
- Type hints bắt buộc trên mọi function
- Docstring bắt buộc trên class và function public
- try/except cho mọi I/O operation
- Không hardcode path — dùng pathlib.Path
- UTF-8 encoding cho mọi file I/O
- logging thay vì print()

## TypeScript/React
```tsx
// ✅ ĐÚNG
interface HerbCardProps {
  herb: HerbEntry
  onSelect?: (herb: HerbEntry) => void
  className?: string
}

export default function HerbCard({ 
  herb, 
  onSelect,
  className = '' 
}: HerbCardProps) {
  return (...)
}

// ❌ SAI — no interface, no default props
export default function HerbCard(props: any) {
  return (...)
}
```

### Rules TypeScript:
- Interface cho mọi props
- Default props cho optional values
- Loading state cho mọi async component
- Error state cho mọi component có thể fail
- 'use client' cho components dùng hooks
- Không dùng 'any' type

## Naming Conventions
Python files:    snake_case.py
Python classes:  PascalCase
Python funcs:    snake_case()
React components: PascalCase.tsx
React hooks:     useHookName.ts
Utilities:       camelCase.ts
Constants:       UPPER_SNAKE_CASE
CSS classes:     kebab-case (Tailwind)

## File Structure
Mỗi feature mới:
missions_hub/
└── [feature_name].py      ← logic
frontend/components/
└── [feature]/
├── index.tsx           ← main component
├── [Feature]Card.tsx   ← sub components
└── types.ts            ← TypeScript types
---

