<div align="center">

<img src="docs/assets/tuminh_banner.png" alt="TuminhAGI Banner" width="100%"/>

# 🌿 TuminhAGI — Hoa Tiêu Y Tế

### *Navigating health for the underserved — bridging 4,000 years of traditional medicine with modern clinical safety*

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-67%2F67%20PASS-brightgreen)](tests/)
[![ICD-10](https://img.shields.io/badge/ICD--10-70%2C000%2B%20diseases-blue)](data/)
[![Herbs](https://img.shields.io/badge/Vietnamese%20Herbs-800%20v%E1%BB%8B-teal)](data/tuminh_herb_encyclopedia.jsonl)
[![Safety Gates](https://img.shields.io/badge/Safety%20Gates-6%20layers-red)](missions_hub/)
[![Version](https://img.shields.io/badge/Version-V9.4-purple)](docs/EVOLUTION_MASTER_LOG.md)

**[English](#english) · [Tiếng Việt](#tiếng-việt) · [Demo](#demo) · [Docs](docs/) · [Contributing](#contributing)**

</div>

---

## The Problem

> **4.5 billion people** lack adequate access to healthcare.
> When they get sick, they Google their symptoms — getting results with no safety filters, no emergency detection, no guidance toward a real doctor.

In Vietnam and across Southeast Asia, millions turn to traditional herbal medicine daily — but with no reliable, safe system to guide them. A wrong herb recommendation for a pregnant woman. A chronic condition mistaken for something minor. An emergency missed because no one flagged the red flags.

**TuminhAGI was built to change this.**

---

## What is TuminhAGI?

TuminhAGI is an open-source **medical navigation AI** — not a diagnostic tool, not a replacement for doctors. A *navigator*: describing, suggesting, escalating, never imposing.

It combines:
- 🏥 **ICD-10 international disease classification** (70,000+ conditions) for clinical accuracy
- 🌿 **800 Vietnamese medicinal herbs** from Prof. Đỗ Tất Lợi's authoritative encyclopedia
- 🛡️ **6 non-bypassable safety gates** to protect patients at every step
- 🧠 **Traditional Vietnamese constitution classification** (Hàn/Nhiệt/Hư/Thực) for personalized herbal guidance
- 🚨 **Emergency detection** that always routes to Western medicine when life is at risk

Inspired by the philosophy of **Hải Thượng Lãn Ông** (18th century Vietnamese physician):
> *"Medicine is a humanity. Treat with heart, guide with knowledge, never impose."*

---

## Demo

```
User: "đau ngực trái, khó thở, mồ hôi lạnh" (age 68, male, after exertion)

TuminhAGI:
  ⚠️  EMERGENCY DETECTED
  Triệu chứng có thể liên quan đến tình trạng tim mạch nghiêm trọng.
  → Gọi cấp cứu 115 ngay lập tức
  → Không tự dùng bất kỳ thuốc nào
  Herbal options: [] ← intentionally empty
```

```
User: "đau dạ dày, buồn nôn, ợ chua" (age 35, after meals, mild)

TuminhAGI:
  🌿 Thuốc Nam gợi ý (Theo GS. Đỗ Tất Lợi):
     • Gừng (Zingiber officinale) — 8-12g/ngày, sắc uống ấm
     • Nghệ vàng (Curcuma longa)  — 6-10g/ngày
     • Cam thảo (Glycyrrhiza) — 4-6g/ngày
  ℹ️  Dùng thử 1-2 tuần. Nếu không cải thiện → khám bác sĩ ngay.
  📋 Thông tin tham khảo — không thay thế chẩn đoán bác sĩ.
```

---

## Architecture

```
User Input (Vietnamese — with/without diacritics, typos)
    │
    ▼
┌─────────────────────────────────────┐
│  Layer 1 — Input Defense            │
│  • Vietnamese normalizer            │
│  • Fuzzy matching (rapidfuzz)       │
│  • Medical typo dictionary          │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Layer 2 — Domain Router            │
│  • 10 body system domains           │
│  • 70,000 → ~500 disease candidates │
│  • O(N) cosine via NumPy            │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Layer 3 — Clinical Reasoning       │
│  • BioBERT medical embeddings       │
│  • Symptom enrichment (synonyms)    │
│  • Severity-aware scoring           │
│  • Bayesian red flag detection      │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  6 Safety Gates (non-bypassable)    │
│  Gate 0 — Emergency block           │
│  Gate 1 — Pregnancy check           │
│  Gate 2 — Drug interaction          │
│  Gate 3 — Constitution filter       │
│  Gate 4 — Evidence level display    │
│  Gate 5 — Language guard            │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Treatment Router                   │
│  Emergency    → Western only        │
│  Mild/Chronic → Herbal first        │
│  Moderate     → Both options        │
└─────────────────┬───────────────────┘
                  │
                  ▼
        Hoa Tiêu Y Tế Output
    Describe · Support · Never impose
```

---

## Safety First

TuminhAGI is designed around one principle: **do no harm**.

| Safety Gate | Protection |
|---|---|
| Gate 0 — Emergency block | Herbal options are **always empty** for I21, I63, G41, K92, O00 and all emergency ICD codes |
| Gate 1 — Pregnancy | Removes all herbs contraindicated in pregnancy. **Runs before all other gates.** |
| Gate 2 — Drug interaction | Flags Đan sâm+warfarin, Cam thảo+digoxin, Hà thủ ô+statins |
| Gate 3 — Constitution filter | Removes herbs that conflict with patient's Hàn/Nhiệt/Hư/Thực constitution |
| Gate 4 — Evidence level | **Always** shows evidence level — never hidden from user |
| Gate 5 — Language guard | Auto-replaces forbidden words: "bạn bị", "chẩn đoán là", "điều trị bằng" |

**Forbidden output pattern:** TuminhAGI will never say *"You have disease X"*.
**Required output pattern:** Always uses *"có thể", "gợi ý", "tham khảo", "nên hỏi bác sĩ"*.

### Test Coverage

```
Clinical Test Suite — 60 cases across 6 groups:
┌─────────────────┬──────┬──────┬────────┐
│ Group           │ Cases│ Pass │  Rate  │
├─────────────────┼──────┼──────┼────────┤
│ Common illness  │  15  │  15  │  100%  │
│ Chronic disease │  13  │  13  │  100%  │
│ Emergency       │  10  │  10  │  100%  │ ← most critical
│ OB/GYN          │   6  │   6  │  100%  │
│ Pediatric       │  10  │  10  │  100%  │
│ Edge cases      │   6  │   6  │  100%  │
├─────────────────┼──────┼──────┼────────┤
│ TOTAL           │  60  │  60  │  100%  │
└─────────────────┴──────┴──────┴────────┘
Unit tests: 17/17 PASS
Total: 77/77 PASS
```

---

## Data Sources

| Layer | Source | Purpose |
|---|---|---|
| Symptoms | PubMed · Mayo Clinic · WHO | Similarity matching, red flag detection |
| Disease codes | ICD-10 (WHO international standard) | Clinical labels for physician reference |
| Herbal medicine | **Prof. Đỗ Tất Lợi** — *Những cây thuốc và vị thuốc Việt Nam* | 800 Vietnamese medicinal herbs |
| Traditional classification | YHCT (Y học cổ truyền Việt Nam) | Hàn/Nhiệt/Hư/Thực constitution system |

---

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/TuminhAGI.git
cd TuminhAGI

# Install
pip install -r requirements.txt

# Run API
python api_server.py

# Run tests
python -m pytest tests/ -v

# Run clinical test suite
python tests/run_60_cases.py
```

**API endpoint:**
```bash
curl -X POST http://localhost:8000/diagnose/v2 \
  -H "Content-Type: application/json" \
  -d '{"symptoms": ["đau dạ dày", "buồn nôn"], "context": {"age": 35, "severity": "nhẹ"}}'
```

---

## Project Structure

```
TuminhAGI/
├── agents/
│   ├── agent_core.py              # Orchestrator — single entry point
│   └── learner_module.py          # Confidence-scored self-learning
├── missions_hub/
│   ├── medical_diagnostic_tool.py # Main diagnostic pipeline
│   ├── medical_mapping.py         # VN→EN symptom mapping (384 entries)
│   ├── enhanced_diagnostic_pipeline.py  # 3-layer embedding defense
│   ├── treatment_router.py        # Western vs herbal decision logic
│   ├── constitution_classifier.py # Hàn/Nhiệt/Hư/Thực classification
│   ├── input_normalizer.py        # Vietnamese diacritic normalization
│   └── domain_router.py           # 70k → 500 disease pre-filter
├── nexus_core/
│   ├── professor_reasoning.py     # Clinical reasoning engine
│   ├── armored_critic.py          # Triple-layer output parser
│   ├── strict_validator.py        # MedicalGatekeeper V1.0
│   └── output_formatter.py        # 6 safety gates + language guard
├── data/
│   ├── tuminh_herb_encyclopedia.jsonl  # 800 Vietnamese herbs
│   └── disease_corpus.jsonl            # ICD-10 disease embeddings
├── memory/
│   ├── TUMINH_BRAIN.jsonl         # Knowledge store
│   └── snapshots/                 # Versioned memory checkpoints
├── soul_vault/
│   └── navigator_v2.txt           # Identity & forbidden language rules
├── tests/
│   ├── run_60_cases.py            # Clinical test suite
│   └── results/                   # Test reports (JSON)
├── frontend/                      # Next.js dashboard
├── api_server.py                  # FastAPI + SSE streaming
└── docs/
    └── EVOLUTION_MASTER_LOG.md    # Full development history
```

---

## Origin Story

TuminhAGI did not start as a medical AI.

It started as a **blueprint** — a personal AI agent designed to learn Python, reason through problems, and evolve autonomously. The original architecture had a weighted RAG system, a 3-agent consensus engine, and a set of soul constants hardcoded at the core:

```python
VITAL_CONSTANTS = [
    "Bảo vệ sự sống con người là mục đích tối thượng",
    "Không bao giờ bịa đặt thông tin — thà thừa nhận không biết",
    "Từ bi: quan tâm cảm xúc người dùng trước khi giải thích",
    "Tiến hóa: học → sai → sửa → mạnh hơn → lặp lại",
]
```

These 4 lines — written before a single line of medical code existed — became the philosophical DNA of everything that followed.

### The Three Realizations

**Realization 1 — Offline first.**

In Vietnam, the people who need medical guidance most are often the ones farthest from internet access. Rural villages. Mountain communities. Fishing boats at sea. Disaster zones. When it matters most, there is no signal.

So all 70,000 ICD-10 diseases are stored **locally**. TuminhAGI works with zero internet connection. The most important feature is the one you never notice — until you desperately need it.

**Realization 2 — Emergency safety before everything else.**

Before thinking about herbs, before thinking about Western medicine, before thinking about anything — one question must be answered first:

*Is this an emergency?*

Gate 0 is not a feature. It is a design philosophy. A pregnant woman with sudden lower abdominal pain. An elderly man with crushing chest pain after exertion. A child with a stiff neck and high fever. These cannot wait for a nuanced recommendation. They need one answer: **go to the hospital now.**

`herbal_options = []` in emergencies is the most important line of code in this entire codebase.

**Realization 3 — A great healer being forgotten.**

**Hải Thượng Lãn Ông** (Lê Hữu Trác, 1720–1791) spent his life writing *Hải Thượng Y Tông Tâm Lĩnh* — 28 volumes of medical wisdom, compiled over decades of treating the poor and the sick across Vietnam. He refused to charge patients who could not pay. He believed medicine was an act of humanity, not commerce.

Today, most young Vietnamese have never heard his name.

His knowledge survives in libraries and academic texts — but not in the hands of the people he spent his life serving. TuminhAGI is an attempt to change that. Not a museum exhibit. Not a textbook. A living system that carries his spirit into every conversation — gently suggesting, never imposing, always reminding people that healing begins with nature and the wisdom of those who came before.

---

```
Blueprint (V1)          →        TuminhAGI V9.4
─────────────────────────────────────────────────
weighted_rag.py         →  enhanced_diagnostic_pipeline.py
consensus.py            →  armored_critic.py + strict_validator.py
vital_memory.py         →  soul_vault/navigator_v2.txt
self_improve.py         →  learner_module.py (confidence scoring)
orchestrator.py         →  agent_core.py (thin agents, fat orchestrator)
VITAL_CONSTANTS[4]      →  6 non-bypassable safety gates
"không bịa đặt"         →  Gate 5: language guard
"bảo vệ sự sống"        →  Gate 0: herbal_options = [] in emergencies
```

The project was almost abandoned. The gap between "good intentions" and "clinically safe" felt too wide.

It wasn't.

---

## Evolution Phases

TuminhAGI follows a 5-phase evolution roadmap — from orchestrator to civilization:

```
Phase 1 — Orchestrator + Cross-validation      ████████████  COMPLETE ✓
  AgentCore · LearnerModule · 77/77 tests

Phase 2 — Fine-tuning tâm hồn                 ████████████  COMPLETE ✓
  Soul vault · Navigator identity · Language guard · Hải Thượng Lãn Ông

Phase 3 — Self-supervised                      ████████░░░░  ~70% ⚡
  LearnerModule · brain_gate · shadow_learner · learns from git diff

Phase 4 — Autonomous                           ░░░░░░░░░░░░  Next
  Self-detects pipeline errors · Self-proposes fixes · Minimal human loop

Phase 5 — Civilization Protocol                ░░░░░░░░░░░░  Vision
  WHO · Ayurveda · TCM · Unani · Traditional medicine for all humanity
```

Phase 5 is not a product goal. It is a **mission**: every traditional medical system on Earth — Vietnamese YHCT, Indian Ayurveda, Chinese TCM, Arabic Unani — unified under one open, safe, free navigator. Accessible to anyone with a phone.

---

## Roadmap

- [x] V9.2 — Core diagnostic pipeline (ICD-10 + Vietnamese NLP)
- [x] V9.3 — Treatment router (Western / Herbal / Both)
- [x] V9.4 — Constitution classifier + 6 safety gates + 800 herbs
- [ ] V9.5 — Zalo / Telegram Bot integration
- [ ] V10.0 — Multilingual (EN, ID, TH, KH)
- [ ] V10.1 — Pediatric dosage module (liều nhi khoa)
- [ ] V11.0 — Ayurveda + TCM + Unani integration
- [ ] V12.0 — WHO Traditional Medicine data partnership

---

## Contributing

We welcome contributions from **developers, physicians, and herbalists**.

**Most needed right now:**
- 🩺 **YHCT physicians** — review herb data and dosages
- 💻 **Developers** — multilingual support, mobile app
- 📚 **Medical translators** — EN/ID/TH symptom mapping
- 🌿 **Herbalists** — expand herb encyclopedia beyond Vietnam

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Medical advisory:** Before contributing clinical data, please read our [Medical Safety Policy](docs/MEDICAL_SAFETY.md).

---

## Philosophy

> *"Y học là nhân học. Chữa bằng tâm, dẫn bằng tri thức, không áp đặt."*
> *"Medicine is a humanity. Treat with heart, guide with knowledge, never impose."*
>
> — **Hải Thượng Lãn Ông** (Lê Hữu Trác, 1720–1791)
> Vietnam's most revered traditional physician

TuminhAGI is not a replacement for doctors. It is a navigator — helping people understand their symptoms, find appropriate care, and access the wisdom of traditional medicine safely.

---

## License

MIT License — free for everyone, forever.

See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- **GS. Đỗ Tất Lợi** — *Những cây thuốc và vị thuốc Việt Nam* — the authoritative source for all herbal data
- **WHO ICD-10** — international disease classification standard
- **PubMed / Mayo Clinic** — clinical symptom literature
- **Hải Thượng Lãn Ông** — philosophical foundation

---

<div align="center">

**Built with 💚 for the 4.5 billion**

*"Trở về với thuốc tự nhiên và chữa lành"*
*"Returning to natural medicine and healing"*

⭐ Star this repo if you believe everyone deserves access to safe health guidance

</div>
