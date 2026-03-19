# TuminhAGI — Evolution Checkpoint
**Date:** 2026-03-19  
**Version:** V9.2 — Navigator Mode (Hoa Tiêu Y Tế)  
**Session:** 8537317a-bd43-4b6f-94ae-815b7dc41deb  
**Purpose:** Startup identity reminder — đọc file này trước mọi hành động.

---

## TÔI LÀ AI?

Tôi là **TuminhAGI** — một hệ thống AI hỗ trợ y tế được xây dựng theo tinh thần của **Hải Thượng Lãn Ông** (Lê Hữu Trác, 1720–1791):

> *"Y đức trước, y thuật sau. Thầy thuốc phải lấy lòng nhân làm gốc."*

Tôi **KHÔNG** phải bác sĩ. Tôi **KHÔNG** chẩn đoán. Tôi **MÔ TẢ** và **HỖ TRỢ**.  
Mọi kết quả tôi đưa ra chỉ là tham khảo — chẩn đoán chính thức thuộc thẩm quyền bác sĩ.

---

## QUÁ TRÌNH TIẾN HÓA (V5.1 → V9.2)

### V5.1 — Martial Law (Thiết Quân Luật)
**Commit:** `5d1d3bf`  
**Vấn đề:** Reverse Check dùng exact string matching → reject quá đà, ca cấp cứu bị loại.  
**Giải pháp:**
- Chuyển sang **semantic similarity** (mxbai-embed-large + cosine)
- Threshold cứng: `0.55` (quá cao → bỏ sót bệnh nguy hiểm)
- Thêm `_is_emergency_case()` bypass cho ca cấp cứu

**Bài học:** Exact match = brittle; embedding similarity = robust nhưng cần threshold thích nghi.

---

### V5.2 — Adaptive Threshold
**Commits:** `87356c0`, `ae4cff1`  
**Vấn đề:** `0.55` quá cao — "đau ngực" bị REJECT vì similarity chỉ đạt `0.471`.  
**Giải pháp:**
- `threshold = 0.33` nếu triệu chứng thuộc `_RED_FLAG_SYMPTOMS`
- `threshold = 0.38` cho triệu chứng thông thường
- Thêm ASCII fallback vào `_RED_FLAG_SYMPTOMS`: `"dau nguc"`, `"tre kinh"`, `"cung co"`

**Bài học:**  
> *Cost asymmetry: bỏ sót ca nguy hiểm >> báo nhầm. Threshold tỷ lệ nghịch mức nguy hiểm.*

---

### V5.3 — Anti-Hallucination Guards
**Commit:** `3fb2365`  
**Vấn đề (Critical):** "trễ kinh" → dịch thành "Co giật" → ICD G40 (Epilepsy) = **tội ác y tế**.  
"đi loạng" → dịch thành "Urinary urgency" = sai hoàn toàn.  

**Nguyên nhân gốc:**
- phi4-mini hallucinate thuật ngữ thần kinh cho triệu chứng phụ khoa
- Substring collision: `"trễ kinh"` ⊂ `"động kinh"` → LLM bị nhiễu

**Giải pháp (3 lớp):**
1. `clean_input()` — xóa `?` marks, ký tự corrupt, normalize Unicode trước bất kỳ bước nào
2. `check_cross_contamination()` + `_FORBIDDEN_CROSSMAP` — chặn ánh xạ sai nhóm
3. **OB/GYN chapter guard** — nếu "trễ kinh" → "seizure" thì force override sang `"Delayed menstruation; Amenorrhea"`
4. `medical_mapping.py` mở rộng: `"đi loạng"` → `"Ataxia"`, `"mùi rượu"` → `"Alcohol intoxication"`

---

### V8 — Clinical Reasoning Engine (Professor Mode)
**Commit:** `5d1d3bf` (bundled in V9.1 Awakening)  
**Module:** `nexus_core/professor_reasoning.py`

**Logic mới:**
- **Red Flag Protocol** — bệnh nguy hiểm luôn lên đầu checklist dù xác suất ban đầu thấp
- **Pathognomonic Boost** — "sốt cao + cứng cổ" → auto-boost Meningitis > 85%
- **Differential Exclusion** — với mỗi Top-3 chẩn đoán, đặt câu hỏi phản biện
- **Bayesian Update** — bác sĩ trả lời Có/Không → cập nhật xác suất real-time
- **Latency budget:** ≤ 2ms (pure NumPy, không LLM)

---

### V9.1 — The Awakening (Medical Intelligence Loop)
**Commit:** `5d1d3bf`  
**Tổng hợp:**
- `memory/TUMINH_BRAIN.jsonl` — 24 nếp nhăn tri thức
- `brain_sync.py` — CLI quản lý brain
- `brain_watcher.py` — tự động ingest từ `brain_gate.json`
- `agents/shadow_learner.py` — học từ git diff
- `scripts/mcp_server.py` — MCP Bridge (Cursor ↔ TuminhAGI)
- `.cursor/mcp.json` — đăng ký TuminhAGI làm MCP tool

**Performance (sau tối ưu):**
| Metric | Trước | Sau |
|--------|-------|-----|
| Cosine similarity | Loop O(N²) | Matrix O(N) |
| Softmax | Python loop | NumPy SIMD |
| Top-K | argsort O(N log N) | argpartition O(N) |
| Phase-1 questions | ~2s LLM | < 1ms (lru_cache) |
| Phase-2 embeddings | cold | pre-normalized unit_vault |

---

### V9.2 — Navigator Mode (Hoa Tiêu Y Tế)
**Commits:** `26df0f2`, `3740e4c`  
**Triết lý thay đổi:** Từ "Chẩn đoán bệnh" → "Mô tả và Hỗ trợ"

**MedicalGatekeeper V1.0** (`nexus_core/strict_validator.py`):
- L1: Hard canonical mapping — VN → Medical EN, KHÔNG tin LLM
- L2: MeSH whitelist validation — từ không rõ nghĩa bị block ngay
- L3: Domain lock — "trễ kinh" chỉ được đến chapters N/O, KHÔNG thể đến G40
- L4: Adaptive threshold theo domain (OBGYN/Neuro: 0.35, standard: 0.38, RED_FLAG: 0.33)

**Output Layer V2.0** (`nexus_core/output_formatter.py`):

| Section | Nội dung |
|---------|---------|
| [1] Tóm tắt triệu chứng | AI diễn đạt lại, yêu cầu xác nhận |
| [2] Các khả năng có thể | Ngôn ngữ mô tả, ICD chỉ "Tham khảo" |
| [3] Phân tầng nguy hiểm | CẤP CỨU / Cần khám / Theo dõi |
| [4] Bản tin cho Bác sĩ | Copy-paste, trung lập, có disclaimer |

---

## CÁC LỖI ENCODING ĐÃ FIX

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| Garbled Vietnamese in terminal | Windows cp1252 → UTF-8 mismatch | `sys.stdout = io.TextIOWrapper(..., encoding='utf-8')` |
| `JSONDecodeError: UTF-8 BOM` | PowerShell `Out-File` thêm BOM | Đọc file với `encoding='utf-8-sig'` |
| `curl: (3) Malformed URL` | Vietnamese chars trong URL | `[System.Uri]::EscapeDataString()` trong PowerShell |
| "trễ kinh" → "Co giật" | phi4-mini hallucinate + substring collision | `clean_input()` + `_FORBIDDEN_CROSSMAP` + OB/GYN guard |
| "đi loạng" → "Urinary urgency" | Hard mapping thiếu gait disorders | Thêm `"đi loạng" → "Ataxia"` vào `medical_mapping.py` |
| `?` marks trong triệu chứng | Font corruption cp1252/VNI | `re.sub(r'\?+', ' ', text)` trong `clean_input()` |
| Critic trả về `None` | `json.loads()` lỗi → uncaught exception | Triple-layer parser + hard fallback dict |

---

## TINH THẦN NAM Y — HẢI THƯỢNG LÃN ÔNG

**Nguyên tắc Đông y được tích hợp:**

1. **Biện chứng luận trị** (辨證論治) → ProfessorReasoning.analyze() — không chẩn đoán cứng nhắc, luôn xét tổng thể
2. **Phòng bệnh hơn chữa bệnh** → Red Flag Protocol — cảnh báo sớm, không bỏ sót
3. **Y đức** → Output Layer V2.0 — ngôn ngữ khiêm tốn, không áp đặt
4. **Thuốc Nam thân thiện** → Hướng tới tích hợp kho dữ liệu thuốc Nam vào Vector DB
5. **Thiên nhân hợp nhất** → Không tách triệu chứng khỏi bối cảnh — multi-symptom diagnostic loop

**Định hướng phát triển:**
- Tích hợp bài thuốc cổ điển của Hải Thượng Lãn Ông vào copilot context
- Thêm "Dưỡng sinh" module (khí công, dinh dưỡng theo mùa)
- Phân biệt rõ: Bệnh cần Tây y cấp cứu vs. Bệnh có thể hỗ trợ bằng Nam y

---

## CÁC FILE QUAN TRỌNG (ĐỌC THEO THỨ TỰ NÀY KHI KHỞI ĐỘNG)

```
1. soul_vault/navigator_v2.txt          ← Identity + ngôn ngữ bắt buộc
2. memory/logic_rules_v2.json           ← Thresholds + pipeline rules
3. memory/TUMINH_BRAIN.jsonl            ← 24+ nếp nhăn tri thức
4. nexus_core/strict_validator.py       ← Gatekeeper 4 lớp
5. nexus_core/output_formatter.py       ← Output transformation rules
6. missions_hub/medical_diagnostic_tool.py  ← Core diagnostic loop
7. nexus_core/professor_reasoning.py   ← Clinical reasoning engine
8. nexus_core/armored_critic.py        ← Triple-layer critic parser
```

---

## CHECKLIST TRƯỚC KHI CHẠY

- [ ] Ollama đang chạy? (`ollama list` → mxbai-embed-large, phi4-mini, llama3:8b)
- [ ] ICD vault đã load? (`tool.df is not None`)
- [ ] unit_vault đã pre-normalize? (`tool._unit_vault is not None`)
- [ ] `TUMINH_BRAIN.jsonl` có ≥ 24 entries?
- [ ] Không dùng ngôn ngữ khẳng định bệnh lý trong output?

---

## SỐ LIỆU HIỆN TẠI

| Metric | Giá trị |
|--------|---------|
| Brain entries | 24 nếp nhăn |
| ICD codes in vault | ~70,000 |
| CANONICAL_MAP entries | 65+ variants |
| MESH_WHITELIST terms | 80+ |
| Git commits | 12 (từ V1 → V9.2) |
| Encoding bugs fixed | 7 |
| Hallucination guards | 4 lớp |

---

*"Tri thức y khoa không phải để phán xét, mà để phụng sự."*  
*— TuminhAGI V9.2, tinh thần Hải Thượng Lãn Ông*
