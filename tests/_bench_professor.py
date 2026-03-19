"""Quick latency benchmark for ProfessorReasoning."""
import sys, time
sys.path.insert(0, ".")
from nexus_core.professor_reasoning import ProfessorReasoning

cases = [
    (
        "sot cao, cung co, dau dau du doi, non vot",
        [
            {"code": "G03", "description": "Meningococcal meningitis", "score": 0.91},
            {"code": "A87", "description": "Viral meningitis",         "score": 0.83},
            {"code": "G00", "description": "Bacterial meningitis",     "score": 0.76},
        ],
        [55.0, 30.0, 15.0],
    ),
    (
        "dau nguc, mo hoi lanh, buon non",
        [
            {"code": "I21", "description": "Acute myocardial infarction", "score": 0.89},
            {"code": "I26", "description": "Pulmonary embolism",          "score": 0.72},
            {"code": "J18", "description": "Pneumonia",                   "score": 0.61},
        ],
        [58.0, 27.0, 15.0],
    ),
    (
        "tieu buot, tieu giat, nuoc tieu duc",
        [
            {"code": "N30", "description": "Acute cystitis",          "score": 0.92},
            {"code": "N10", "description": "Acute pyelonephritis",    "score": 0.81},
            {"code": "N39", "description": "Urinary tract infection", "score": 0.74},
        ],
        [52.0, 31.0, 17.0],
    ),
    (
        "kho tho, ho keo dai, khho khe",
        [
            {"code": "J45", "description": "Asthma",                     "score": 0.88},
            {"code": "J18", "description": "Pneumonia",                  "score": 0.79},
            {"code": "J22", "description": "Lower respiratory infection", "score": 0.65},
        ],
        [54.0, 31.0, 15.0],
    ),
]

print()
print("=" * 65)
print("  ProfessorReasoning — Latency Benchmark (100 reps each)")
print("=" * 65)
total_ms = []
for symptoms, cands, probs in cases:
    for _ in range(10):
        ProfessorReasoning.analyze(symptoms, cands, probs)
    t0 = time.perf_counter()
    for _ in range(100):
        r = ProfessorReasoning.analyze(symptoms, cands, probs)
    avg = (time.perf_counter() - t0) * 1000 / 100
    total_ms.append(avg)
    tag = "PASS" if avg < 2.0 else "FAIL"
    print(f"  {tag}  {symptoms[:45]:<45}  {avg:.3f} ms")
    print(f"       red_flags={len(r.red_flags)}  boosts={len(r.pathognomonic_boosts)}  excl={len(r.differential_exclusions)}")

print()
mean_ms = sum(total_ms) / len(total_ms)
max_ms  = max(total_ms)
print(f"  Mean: {mean_ms:.3f} ms  |  Max: {max_ms:.3f} ms")
all_pass = all(m < 2.0 for m in total_ms)
print(f"  Target < 2 ms: {'ALL PASS' if all_pass else 'SOME FAIL'}")
print("=" * 65)
