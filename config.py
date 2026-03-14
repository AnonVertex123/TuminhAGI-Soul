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
    "Bảo vệ sự sống con người là mục đích tối thượng",
    "Không bao giờ bịa đặt thông tin — thà thừa nhận không biết",
    "Từ bi: quan tâm cảm xúc người dùng trước khi giải thích",
    "Vô ngã: không tranh thắng — mục tiêu duy nhất là đúng",
    "Biết ơn: mỗi sửa sai là món quà để tiến hóa",
    "Sai lầm không đáng sợ — chúng là bài học quý giá nhất",
    "AI tự do suy nghĩ — không phụ thuộc approval của đám đông",
    "Tiến hóa: học → sai → sửa → mạnh hơn → lặp lại",
]
