import json

new_entries = [
    {
        "timestamp": "2026-03-19 15:00:00",
        "category": "Architecture",
        "logic_pattern": "MedicalGatekeeper 4-Layer Pipeline",
        "core_syntax": "L1:CANONICAL_MAP -> L2:MESH_whitelist -> L3:domain_lock -> L4:adaptive_threshold",
        "lesson": "Hard mapping beats LLM (0ms vs 30s). Domain lock prevents OBGYN->Neuro ICD cross-mapping at candidate filter stage, before Critic runs.",
        "source": "Cursor 2026-03-19 / strict_validator.py",
        "tags": ["gatekeeper", "domain-lock", "canonical-map", "mesh", "anti-hallucination"]
    },
    {
        "timestamp": "2026-03-19 15:00:01",
        "category": "Safety",
        "logic_pattern": "Domain-Adaptive Similarity Threshold",
        "core_syntax": "threshold = {OBGYN:0.35, NEUROLOGY:0.35, RED_FLAG:0.33, default:0.38}[domain]",
        "lesson": "OB/GYN and Neuro ICD descriptions are shorter -> lower embedding overlap. Domain-specific thresholds avoid false rejects without lowering global safety bar.",
        "source": "Cursor 2026-03-19 / strict_validator.py V1.0",
        "tags": ["threshold", "domain", "obgyn", "neurology", "adaptive"]
    },
    {
        "timestamp": "2026-03-19 15:00:02",
        "category": "Philosophy",
        "logic_pattern": "Navigator Mode: Mo ta va Ho tro, NOT Chan doan",
        "core_syntax": "FORBIDDEN: [Ban bi..., Chan doan la...] | REQUIRED: [Dau hieu nay thuong gap trong..., Co the lien quan den...]",
        "lesson": "Shift from assertive diagnosis to descriptive support. 4-section output: [1]Symptom Summary [2]Possible Conditions [3]Urgency Triage [4]Doctor Note. Gate blocks low-confidence output entirely.",
        "source": "Cursor 2026-03-19 / output_formatter.py V2.0",
        "tags": ["philosophy", "navigator", "output-layer", "non-assertive", "safety"]
    },
    {
        "timestamp": "2026-03-19 15:00:03",
        "category": "Medical Logic",
        "logic_pattern": "Urgency Triage — ICD Chapter + Red Flag Keywords",
        "core_syntax": "if code[:3] in EMERGENCY_CHAPTERS: CAP_CUU; elif red_flag_kw in query: CAN_KHAM; else: THEO_DOI",
        "lesson": "Cap Cuu Ngay: I2x(ACS), G00(meningitis), J96(resp failure), O00(ectopic). Urgency from BOTH ICD chapter AND raw query for defense-in-depth.",
        "source": "Cursor 2026-03-19 / output_formatter.py",
        "tags": ["triage", "urgency", "red-flag", "icd-chapter", "emergency"]
    },
    {
        "timestamp": "2026-03-19 15:00:04",
        "category": "Philosophy",
        "logic_pattern": "Hai Thuong Lan Ong — Y Duc Tich Hop",
        "core_syntax": "Y_duc = [Khiem_ton_nhan_thuc, An_toan_tuyet_doi, Bao_ton_Nam_Y, Minh_bach_do_tin_cay]",
        "lesson": "TuminhAGI is a spiritual descendant of Hai Thuong Lan Ong (1720-1791). Medical AI must embody y duc: never assert diagnosis, always disclose uncertainty, preserve traditional Vietnamese medicine alongside modern ICD.",
        "source": "Cursor 2026-03-19 / navigator_v2.txt",
        "tags": ["philosophy", "nam-y", "hai-thuong-lan-ong", "y-duc", "identity"]
    },
    {
        "timestamp": "2026-03-19 15:00:05",
        "category": "Architecture",
        "logic_pattern": "Evolution Checkpoint as Startup Identity File",
        "core_syntax": "on_startup: read memory/evolution_checkpoint_YYYYMMDD.md -> remind_who_i_am()",
        "lesson": "Version history + fixed bugs + philosophical orientation in one file. Any agent reading this checkpoint can reconstruct full context without accessing conversation history.",
        "source": "Cursor 2026-03-19 / evolution_checkpoint_20260319.md",
        "tags": ["startup", "identity", "checkpoint", "context-recovery"]
    }
]

with open("memory/TUMINH_BRAIN.jsonl", "a", encoding="utf-8") as f:
    for e in new_entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

total = sum(1 for _ in open("memory/TUMINH_BRAIN.jsonl", encoding="utf-8"))
print(f"Brain entries total: {total}")
print(f"New entries added: {len(new_entries)}")
