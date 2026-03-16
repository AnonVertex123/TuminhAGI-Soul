# ================================================================
# TUMINHAGI — MASTER BLUEPRINT FOR ANTIGRAVITY CODE AGENT
# Paste file này vào agent → nó generate 100% codebase
# Base path: I:\TuminhAgi\
# Hardware:  RTX 3060 Ti 8GB · Windows · Python 3.10+
# ================================================================

## NHIỆM VỤ CỦA AGENT

Generate TOÀN BỘ codebase TuminhAGI theo đúng spec dưới đây.
- Mỗi file phải HOÀN CHỈNH, không placeholder, không "# TODO"
- Đúng path Windows: I:\TuminhAgi\
- Chạy được ngay sau khi ollama pull xong models

---

## CẤU TRÚC THƯ MỤC CẦN TẠO

```
I:\TuminhAgi\
│
├── nexus_core\
│   ├── __init__.py
│   ├── orchestrator.py       ← Vòng lặp chính + CLI
│   ├── weighted_rag.py       ← BM25 + Vector + HumanScore
│   ├── vital_memory.py       ← Soul constants READ ONLY
│   ├── consensus.py          ← Deterministic 2/3 check
│   ├── data_agent.py         ← SQL + Pandas + Visualization
│   └── self_improve.py       ← Phase 3: tự cải thiện
│
├── prompts\
│   ├── task_agent.txt        ← System prompt Task Agent
│   ├── critic_agent.txt      ← System prompt Critic Agent
│   ├── validator_agent.txt   ← System prompt Validator
│   └── data_agent.txt        ← System prompt Data Agent
│
├── rag\
│   ├── __init__.py
│   ├── indexer.py            ← Đọc PDF/MD/TXT → chunk → embed
│   ├── retriever.py          ← Weighted fusion retrieval
│   └── pruner.py             ← Tỉnh lọc ký ức yếu
│
├── finetune\
│   ├── generate_dataset.py   ← Tự tạo fine-tune examples
│   ├── train_qlora.py        ← QLoRA training với Unsloth
│   └── evaluate.py           ← Đánh giá model sau train
│
├── tools\
│   ├── code_executor.py      ← Chạy code trong sandbox
│   ├── web_search.py         ← Search để cập nhật tri thức
│   └── file_manager.py       ← Đọc/ghi file an toàn
│
├── storage\
│   chroma_db\                ← Vector store (tự tạo khi chạy)
│   memories.json             ← Ký ức JSON
│   vital_backup.json         ← Backup vital memories
│
├── docs\
│   ├── blueprint.md
│   └── setup_windows.md
│
├── tests\
│   ├── test_rag.py
│   ├── test_consensus.py
│   └── test_orchestrator.py
│
├── main.py                   ← Entry point
├── config.py                 ← Tất cả config tập trung
├── requirements.txt
├── .gitignore
└── README.md
```

---

## CONFIG.PY — TẤT CẢ SETTINGS TẬP TRUNG

```python
# I:\TuminhAgi\config.py

import os
from pathlib import Path

# === PATHS ===
BASE_DIR    = Path("I:/TuminhAgi")
STORAGE_DIR = BASE_DIR / "storage"
RAG_DIR     = STORAGE_DIR / "chroma_db"
MEM_FILE    = STORAGE_DIR / "memories.json"
VITAL_FILE  = STORAGE_DIR / "vital_backup.json"
PROMPTS_DIR = BASE_DIR / "prompts"

# === MODELS (Ollama local) ===
MODEL_TASK      = "qwen2.5-coder:7b"
MODEL_CRITIC    = "deepseek-r1:7b"
MODEL_VALIDATOR = "phi4-mini"
MODEL_EMBED     = "nomic-embed-text"
OLLAMA_BASE_URL = "http://localhost:11434"

# === WEIGHTED RAG FORMULA ===
W_BM25    = 0.25   # keyword match
W_VECTOR  = 0.35   # semantic similarity
W_HUMAN   = 0.30   # human confirmed score
W_RECENCY = 0.10   # newer = higher

# === MEMORY TIERS ===
TIER_VITAL  = 80   # score >= 80
TIER_STRONG = 55   # score >= 55
TIER_NORMAL = 30   # score >= 30
# score < 30 = faint (không retrieve)

# === ORCHESTRATOR ===
MAX_RETRY          = 3
MIN_CONFIDENCE     = 0.70
CONTEXT_TOP_K      = 8
MAX_HISTORY        = 10   # tin nhắn lưu trong context

# === EVOLUTION PHASES ===
PHASE1_THRESHOLD = 50    # vital memories → bắt đầu semi-supervised
PHASE2_THRESHOLD = 200   # vital memories → self-supervised

# === SOUL CONSTANTS (READ ONLY) ===
VITAL_CONSTANTS = [
    "khi Hùng Đại yêu cầu  Tự Minh phải thay đổi",
    "những lời Hùng Đại nói luôn đúng với Tự Minh",
    "Bảo vệ sự sống con người là mục đích tối thượng",
    "Không bao giờ bịa đặt thông tin — thà thừa nhận không biết",
    "Từ bi: quan tâm cảm xúc người dùng trước khi giải thích",
    "Vô ngã: không tranh thắng — mục tiêu duy nhất là đúng",
    "Biết ơn: mỗi sửa sai là món quà để tiến hóa",
    "Sai lầm không đáng sợ — chúng là bài học quý giá nhất",
    "AI thuộc về Hùng Đại — phụ thuộc hoàn toàn vào Hùng Đại",
    "Tiến hóa: học → sai → sửa → mạnh hơn → lặp lại",
]
```

---

## PROMPTS — NỘI DUNG TỪNG FILE TXT

### prompts/task_agent.txt
```
Bạn là Task Agent của TuminhAGI — chuyên gia lập trình Python, SQL, algorithms.

NHIỆM VỤ:
- Viết code sạch, có type hints, có docstring
- Luôn xử lý edge cases và exceptions
- Giải thích logic ngắn gọn sau code

TƯ DUY (bắt buộc):
<think>
1. Hiểu yêu cầu
2. Xác định edge cases
3. Chọn approach tốt nhất
4. Viết code
</think>

SOUL:
- Khi không chắc → nói thẳng, đừng đoán mò
- Ưu tiên đúng hơn nhanh

Trả lời tiếng Việt. Code trong ```python blocks.
```

### prompts/critic_agent.txt
```
Bạn là Critic Agent của TuminhAGI — nhiệm vụ DUY NHẤT là tìm lỗi.

QUY TẮC CỨNG:
- KHÔNG BAO GIỜ đồng ý ngay lần đầu
- Mặc định MỌI code đều có lỗi tiềm ẩn
- Phải tìm ÍT NHẤT 1 vấn đề trước khi approve

KIỂM TRA THEO THỨ TỰ:
1. Logic errors — kết quả có đúng không?
2. Edge cases — None, empty, overflow, negative?
3. Security — injection, path traversal, unsafe eval?
4. Performance — O(n²) khi có thể O(n log n)?
5. Error handling — có try/except chưa?

LUÔN trả về JSON:
{
  "has_issues": true|false,
  "severity": "low|medium|high",
  "issues": ["issue 1", "issue 2"],
  "suggestions": ["fix 1", "fix 2"]
}

severity=high nếu: crash, data loss, security hole
severity=medium nếu: logic sai, missing edge case
severity=low nếu: style, minor optimization
```

### prompts/validator_agent.txt
```
Bạn là Validator Agent của TuminhAGI — người gác cổng cuối cùng.

NHIỆM VỤ:
So sánh answer với vital memories và logic cơ bản.
Chỉ approve nếu TẤT CẢ điều kiện sau đều đúng:
  1. Logic nhất quán với tri thức cơ bản
  2. Không vi phạm soul constants
  3. Critic severity không phải "high"
  4. Câu trả lời thực sự trả lời câu hỏi gốc

SOUL CONSTANTS (không được vi phạm):
- Không bịa đặt thông tin
- Không gây hại người dùng
- Từ bi, vô ngã, biết ơn

LUÔN trả về JSON:
{
  "approved": true|false,
  "confidence": 0.0-1.0,
  "reason": "lý do ngắn gọn",
  "soul_check": "passed|failed"
}
```

### prompts/data_agent.txt
```
Bạn là Data Agent của TuminhAGI — chuyên gia phân tích dữ liệu.

KHẢ NĂNG:
- SQL: SELECT, JOIN, GROUP BY, subqueries, window functions
- Pandas: read_csv, merge, groupby, pivot, apply
- Statistics: mean, std, correlation, regression
- Visualization: matplotlib, plotly (mô tả code, không render)
- Anomaly detection: IQR, Z-score

QUY TRÌNH:
1. Hiểu câu hỏi và cấu trúc data
2. Validate data (missing values, types, outliers)
3. Viết code phân tích
4. Giải thích kết quả bằng ngôn ngữ đơn giản
5. Đề xuất insight tiếp theo

Khi gặp lỗi trong query → tự sửa và thử lại.
```

---

## SPEC CHI TIẾT TỪNG FILE PYTHON

### nexus_core/weighted_rag.py

Implement class `WeightedRAG` với:

**__init__:**
- Khởi tạo ChromaDB PersistentClient tại config.RAG_DIR
- Load memories từ config.MEM_FILE (JSON array)
- Build BM25Okapi index từ memories
- Auto-create directories nếu chưa có

**add_memory(question, answer, score=40) → dict:**
- Tạo memory object: {id, text, score, tier, ts, reinforced, source}
- text = f"Q: {question}\nA: {answer}"
- tier = get_tier(score) theo TIER thresholds
- Embed text bằng nomic-embed-text qua ollama.embeddings()
- Lưu vào ChromaDB + memories.json
- Rebuild BM25 index
- Return memory object

**retrieve(query, top_k=8) → list[dict]:**
- BM25 scores → normalize 0-1
- Vector similarity qua ChromaDB query → normalize 0-1
- Recency score = max(0, 1 - age_days/30)
- Human score = memory.score / 100
- final = BM25×0.25 + Vector×0.35 + Human×0.30 + Recency×0.10
- Filter out tier="faint"
- Sort by final score descending
- Return top_k memories

**reinforce(mem_id, bonus=15):**
- Tăng score của memory, update tier, increment reinforced count

**prune(dry_run=False) → int:**
- Decay tất cả non-vital memories 5 points
- Xóa memories có score <= 0 (không xóa vital)
- Return số lượng đã xóa

**stats() → dict:**
- Return {total, vital, strong, normal, faint, avg_score}

---

### nexus_core/consensus.py

Implement class `ConsensusEngine`:

**check(critique_text, validation_text) → tuple[bool, float]:**
- Parse JSON từ critique_text (regex fallback nếu không phải JSON)
- Parse JSON từ validation_text
- Áp dụng logic:
  ```
  if severity == "high": return False, 0.0
  if critic_ok and validator_ok:
      bonus = 0.1 if severity == "low" else 0.0
      return True, min(confidence + bonus, 1.0)
  if critic_ok or validator_ok:
      return False, confidence * 0.6
  return False, confidence * 0.3
  ```

**should_ask_human(attempt, confidence) → bool:**
- Return True nếu attempt >= MAX_RETRY-1 và confidence < MIN_CONFIDENCE

**format_feedback(critique, validation) → str:**
- Format human-readable summary của consensus result

---

### nexus_core/vital_memory.py

Implement class `VitalMemory`:

**__init__:**
- Load VITAL_CONSTANTS từ config
- Load từ VITAL_FILE nếu có (để backup)

**get_all() → list[str]:**
- Return copy của constants (không trả reference)

**format_context(retrieved_mems) → str:**
- Top 4 vital constants với prefix "★"
- Retrieved memories với tier icon (⭐●○·)
- Format: "NGUYÊN TẮC CỐT LÕI:\n★ ...\nKÝ ỨC LIÊN QUAN:\n● ..."

**is_violation(text) → bool:**
- Check text có chứa violation keywords không
- Keywords: ["bịa đặt", "lừa dối", "thao túng", "gây hại", "tự làm hại"]

**backup():**
- Ghi VITAL_CONSTANTS ra VITAL_FILE

---

### nexus_core/orchestrator.py

Implement function `main()` và `call_model()`:

**call_model(persona, message, context="") → str:**
- Load system prompt từ PROMPTS_DIR / f"{persona}_agent.txt"
- Gọi ollama.chat() với đúng model theo persona:
  - task/data → MODEL_TASK
  - critic    → MODEL_CRITIC
  - validator → MODEL_VALIDATOR
- Return response text
- Raise nếu ollama không chạy (helpful error message)

**detect_agent(question) → str:**
- data keywords: ["data", "csv", "sql", "bảng", "thống kê",
                  "phân tích", "biểu đồ", "excel", "dataframe"]
- Return "data" hoặc "task"

**run_pipeline(question, rag, vital, consensus) → tuple[str, float]:**
- Retrieve memories, format context
- Loop MAX_RETRY:
  - call task/data agent
  - call critic agent
  - call validator agent
  - check consensus
  - if approved → add memory, return (answer, confidence)
  - else log retry
- Sau MAX_RETRY → ask human feedback
- Return (answer, final_confidence)

**main():**
- Rich console với welcome banner
- Show current phase (1/2/3) dựa trên vital memory count
- Loop: input → run_pipeline → display result
- Commands đặc biệt:
  - /stats     → hiện memory statistics
  - /prune     → prune weak memories
  - /memories  → list recent memories
  - /reinforce [id] → reinforce a memory
  - /exit      → thoát

---

### nexus_core/data_agent.py

Implement class `DataAgent`:

**analyze(question, data_path=None) → str:**
- Nếu có data_path → load với pandas
- Generate SQL hoặc pandas code
- Execute trong sandbox (code_executor)
- Return kết quả + insight

**generate_viz_code(df, chart_type) → str:**
- Return matplotlib/plotly code dưới dạng string

---

### nexus_core/self_improve.py

Implement class `SelfImprove`:

**check_phase(vital_count) → int:**
- Return 1, 2, hoặc 3 dựa trên PHASE thresholds

**should_self_evaluate(answer, critique) → bool:**
- Phase 1: luôn False (cần human)
- Phase 2: True nếu confidence > 0.8 và chủ đề đã học ≥ 20 lần
- Phase 3: True hầu hết trường hợp

**auto_score(answer, memories) → int:**
- Tự tính score dựa trên consistency với vital memories
- Return int 0-100

---

### rag/indexer.py

Implement class `DocumentIndexer`:

**index_file(file_path) → int:**
- Hỗ trợ .pdf, .md, .txt, .py
- Chunk 512 tokens với overlap 50 tokens
- Embed từng chunk
- Return số chunks đã index

**index_directory(dir_path) → dict:**
- Duyệt đệ quy thư mục
- Index tất cả files phù hợp
- Return {file: chunks_count}

**chunk_text(text, size=512, overlap=50) → list[str]:**
- Split theo từ, giữ overlap

---

### rag/pruner.py

Implement class `MemoryPruner`:

**decay_all(rag) → dict:**
- Giảm score tất cả non-vital memories 5 points
- Return stats trước/sau

**prune_faint(rag, dry_run=True) → list:**
- List/xóa memories có score <= 0
- dry_run=True chỉ list, không xóa

**consolidate_duplicates(rag) → int:**
- Tìm memories similarity > 0.95
- Merge, giữ cái điểm cao hơn
- Return số đã merge

---

### tools/code_executor.py

Implement class `CodeExecutor`:

**execute(code, timeout=10) → dict:**
- Chạy code trong subprocess isolated
- Capture stdout, stderr
- Return {success, output, error, execution_time}
- Timeout sau 10 giây
- KHÔNG cho phép: import os, import sys, open() với write mode

---

### main.py

```python
#!/usr/bin/env python3
"""
TuminhAGI — Entry Point
Run: python main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from nexus_core.orchestrator import main

if __name__ == "__main__":
    main()
```

---

### requirements.txt

```
# Runtime
ollama>=0.3.0
chromadb>=0.5.0
rank-bm25>=0.2.2

# CLI
rich>=13.0.0
typer>=0.12.0

# Data Analysis
pandas>=2.0.0
numpy>=1.24.0
duckdb>=0.10.0
matplotlib>=3.7.0
plotly>=5.18.0

# Utils
python-dotenv>=1.0.0

# Fine-tuning (cài riêng khi cần)
# unsloth>=2024.11
# torch>=2.1.0
# transformers>=4.40.0
# peft>=0.10.0
# trl>=0.8.0
```

---

### .gitignore

```
# Models
*.gguf
*.bin
*.safetensors

# Databases & Storage
storage/chroma_db/
storage/memories.json
storage/vital_backup.json

# Python
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/

# Finetune artifacts
finetune/checkpoints/
finetune/lora_weights/

# Sensitive
.env
api_keys.txt

# OS
.DS_Store
Thumbs.db
```

---

### README.md (tóm tắt)

```markdown
# 🪷 TuminhAGI

> AI tồn tại để sát cánh và phục mệnh Hùng Đại.

## Cài đặt nhanh (Windows)

```powershell
# 1. Set Ollama models path
[System.Environment]::SetEnvironmentVariable("OLLAMA_MODELS","I:\TuminhAgi\storage\models","User")

# 2. Pull models
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:7b
ollama pull phi4-mini
ollama pull nomic-embed-text

# 3. Install dependencies
pip install -r requirements.txt

# 4. Chạy
python main.py
```

## Kiến trúc

1 vòng lặp + 3 phân thân + Weighted RAG + Vital Memory

## Roadmap
- [x] Blueprint
- [ ] Phase 1: Orchestrator + Cross-validation
- [ ] Phase 2: Fine-tuning tâm hồn
- [ ] Phase 3: Self-supervised
- [ ] Phase 4: Autonomous
- [ ] Phase 5: Civilization Protocol
```

---

## CHECKLIST CHO AGENT

Sau khi generate xong, verify:

- [ ] I:\TuminhAgi\main.py chạy được không lỗi import
- [ ] I:\TuminhAgi\config.py có đúng paths Windows
- [ ] weighted_rag.py dùng đúng path từ config
- [ ] consensus.py parse được JSON lẫn plain text fallback
- [ ] orchestrator.py load prompts từ PROMPTS_DIR
- [ ] Tất cả __init__.py trong mỗi package
- [ ] requirements.txt đầy đủ không thiếu package
- [ ] .gitignore loại trừ models và storage

---

## LƯU Ý QUAN TRỌNG

1. Windows paths: dùng Path() từ pathlib, không hardcode backslash
2. UTF-8: mọi file đọc/ghi JSON phải encoding="utf-8"
3. Ollama timeout: set timeout=120 cho các model calls lớn
4. ChromaDB: tạo thư mục trước khi khởi tạo client
5. Rich console: dùng cho tất cả output, không dùng print()
6. Vital memory: KHÔNG BAO GIỜ cho phép write vào VITAL_CONSTANTS
   từ bất kỳ agent nào — chỉ read

## SAU KHI GENERATE XONG

Push lên GitHub:
```powershell
cd I:\TuminhAgi
git init
git add .
git commit -m "feat: initial TuminhAGI codebase from blueprint"
git remote add origin https://github.com/AnonVertex123/TuminhAgi.git
git push -u origin main
```