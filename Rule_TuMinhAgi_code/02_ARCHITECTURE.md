# 02 — Kiến trúc hệ thống

## Tổng quan

Layer 1 — Input Defense
input_normalizer.py     ← dấu/không dấu/typo
domain_router.py        ← 70k → 500 diseases
↓
Layer 2 — Clinical Reasoning
enhanced_diagnostic_pipeline.py
professor_reasoning.py
armored_critic.py ← PROTECTED
↓
Layer 3 — 6 Safety Gates
strict_validator.py ← PROTECTED
↓
Layer 4 — Treatment Router
treatment_router.py
constitution_classifier.py
↓
Layer 5 — Output
output_formatter.py ← language guard
↓
Hoa Tiêu Y Tế Output

## Protected Files — KHÔNG SỬA
nexus_core/armored_critic.py      ← Triple-layer parser
nexus_core/strict_validator.py    ← MedicalGatekeeper
nexus_core/professor_reasoning.py ← Clinical engine
soul_vault/navigator_v2.txt       ← Identity
memory/TUMINH_BRAIN.jsonl         ← Knowledge store

## Frontend Architecture
4-column layout (FIXED):
┌──────┬──────────┬──────────────────┬─────────────┐
│ 50px │  220px   │    flex-1        │   320px     │
│ Icon │ Sidebar  │  Main Content    │ Minh Biên   │
└──────┴──────────┴──────────────────┴─────────────┘
components/
├── clickup/     ← PROTECTED (core UI shell)
├── emergency/   ← emergency feature
├── medical/     ← diagnosis UI
├── health/      ← health profile
└── shared/      ← reusable components

## API Endpoints
POST /diagnose/v2          ← main diagnosis
GET  /diagnose/stream      ← SSE streaming
POST /api/emergency/hospitals ← nearby hospitals
GET  /health               ← backend status
---

*** End Patch
