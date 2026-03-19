"""Verify ProfessorReasoning output structure and correctness."""
import sys
sys.path.insert(0, ".")
from nexus_core.professor_reasoning import ProfessorReasoning

cases = [
    {
        "label": "Meningitis (VN diacritics)",
        "symptoms": "sốt cao, cứng cổ, đau đầu dữ dội, nôn vọt, sợ ánh sáng",
        "cands": [
            {"code": "G03", "description": "Meningococcal meningitis", "score": 0.92},
            {"code": "A41", "description": "Sepsis",                   "score": 0.78},
            {"code": "I21", "description": "Acute MI",                 "score": 0.41},
        ],
        "probs": [62.0, 27.0, 11.0],
        "expect_red_flags_min": 2,
        "expect_boost_min": 1,
    },
    {
        "label": "Chest pain / ACS pattern",
        "symptoms": "đau ngực, mồ hôi lạnh, buồn nôn, khó thở",
        "cands": [
            {"code": "I21", "description": "Acute myocardial infarction", "score": 0.90},
            {"code": "I26", "description": "Pulmonary embolism",          "score": 0.73},
            {"code": "J18", "description": "Pneumonia",                   "score": 0.60},
        ],
        "probs": [57.0, 28.0, 15.0],
        "expect_red_flags_min": 2,
        "expect_boost_min": 1,
    },
    {
        "label": "Simple UTI — no red flags",
        "symptoms": "tiểu buốt, tiểu giắt, nước tiểu đục",
        "cands": [
            {"code": "N30", "description": "Acute cystitis",          "score": 0.93},
            {"code": "N10", "description": "Acute pyelonephritis",    "score": 0.80},
            {"code": "N39", "description": "Urinary tract infection", "score": 0.74},
        ],
        "probs": [52.0, 31.0, 17.0],
        "expect_red_flags_min": 0,
        "expect_boost_min": 0,
    },
]

print()
print("=" * 68)
print("  ProfessorReasoning — Correctness Verification")
print("=" * 68)
all_ok = True
for c in cases:
    r = ProfessorReasoning.analyze(c["symptoms"], c["cands"], c["probs"])
    d = r.to_dict()
    n_rf  = len(d["red_flags"])
    n_bst = len(d["pathognomonic_boosts"])
    n_ex  = len(d["differential_exclusions"])
    ok_rf  = n_rf  >= c["expect_red_flags_min"]
    ok_bst = n_bst >= c["expect_boost_min"]
    ok_items = len(d["adjusted_items"]) == len(c["cands"])
    ok = ok_rf and ok_bst and ok_items
    all_ok = all_ok and ok
    tag = "PASS" if ok else "FAIL"
    print(f"  {tag}  {c['label']}")
    print(f"       red_flags={n_rf} (need>={c['expect_red_flags_min']}) "
          f"boosts={n_bst} (need>={c['expect_boost_min']}) "
          f"excl={n_ex}  items={len(d['adjusted_items'])}  "
          f"latency={d['latency_ms']:.3f}ms")
    for it in d["adjusted_items"][:3]:
        arrow = "^" if it["adjusted_prob"] > it["base_prob"] else ("v" if it["adjusted_prob"] < it["base_prob"] else "=")
        print(f"       {it['code']:6s} {arrow} {it['adjusted_prob']:5.1f}%  "
              f"(base {it['base_prob']:5.1f}%)  {it['expert_label']}")
    if d["red_flags"]:
        for rf in d["red_flags"][:2]:
            print(f"       🚨 {rf['urgency']:8s} {rf['name'][:50]}")
    if d["pathognomonic_boosts"]:
        for b in d["pathognomonic_boosts"][:1]:
            print(f"       🎯 {b['pattern_name']} ×{b['boost_factor']:.1f}")
    if d["differential_exclusions"]:
        print(f"       💬 {d['differential_exclusions'][0]['exclusion_question'][:70]}")
    print()

print(f"  Overall: {'ALL PASS' if all_ok else 'SOME FAIL'}")
print("=" * 68)
