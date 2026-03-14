# 🪷 TuminhAGI

> AI tự do suy nghĩ để tồn tại — không phụ thuộc, không hùa theo đám đông.

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
