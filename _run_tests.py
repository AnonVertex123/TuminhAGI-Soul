"""Runs the enhanced pipeline tests and writes results to _test_results.txt"""
import sys
import os
import asyncio
import traceback
import io

# Fix Windows encoding before any print
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, "I:/TuminhAgi")
os.chdir("I:/TuminhAgi")

results = []

def log(msg):
    print(msg)
    results.append(msg)

# ── Test helper ────────────────────────────────────────────────────────────────
def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

# ── Load pipeline once ─────────────────────────────────────────────────────────
log("Loading EnhancedDiagnosticPipeline (minilm)...")
try:
    from missions_hub.enhanced_diagnostic_pipeline import (
        EnhancedDiagnosticPipeline, SymptomContext
    )
    pipeline = EnhancedDiagnosticPipeline(embed_model="minilm")
    log(f"Pipeline loaded. Model: {pipeline.embedder.model_name}")
    log(f"Corpus size: {len(pipeline.corpus.diseases)} diseases")
except Exception as e:
    log(f"FATAL: Could not load pipeline: {e}")
    traceback.print_exc()
    sys.exit(1)

# ── TEST 1 ─────────────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("TEST 1: Cardiac emergency (đau ngực trái + khó thở, age=68)")
try:
    ctx = SymptomContext(
        raw_symptoms=["đau ngực trái", "khó thở"],
        trigger="gắng sức", age=68, sex="nam",
    )
    result = run(pipeline.diagnose(ctx))
    nav = pipeline.to_navigator_output(result)
    top = nav["candidates"][0] if nav["candidates"] else {}
    log(f"  is_emergency : {nav['is_emergency']}")
    log(f"  top candidate: {top.get('name_vn')} [{top.get('urgency')}] score={top.get('score')}")
    for c in nav["candidates"]:
        log(f"    [{c['urgency']:10}] {c['disease_id']} {c['name_vn']} score={c['score']}")
    assert top.get("urgency") == "emergency", f"Expected emergency, got {top.get('urgency')}"
    log("  RESULT: PASS")
except Exception as e:
    log(f"  RESULT: FAIL — {e}")
    traceback.print_exc()

# ── TEST 2 ─────────────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("TEST 2: OBGYN guard (trễ kinh + đau bụng dưới, sex=nữ)")
try:
    ctx2 = SymptomContext(
        raw_symptoms=["trễ kinh", "đau bụng dưới"],
        sex="nữ",
    )
    result2 = run(pipeline.diagnose(ctx2))
    nav2 = pipeline.to_navigator_output(result2)
    ids = [c["disease_id"] for c in nav2["candidates"]]
    log(f"  Candidate IDs: {ids}")
    for c in nav2["candidates"]:
        log(f"    [{c['urgency']:10}] {c['disease_id']} {c['name_vn']} score={c['score']}")
    assert "G40" not in ids, f"G40 appeared: {ids}"
    log("  RESULT: PASS (G40 not in candidates)")
except Exception as e:
    log(f"  RESULT: FAIL — {e}")
    traceback.print_exc()

# ── TEST 3 ─────────────────────────────────────────────────────────────────────
log("\n" + "="*60)
log("TEST 3: Gait ataxia not emergency (đi loạng choạng + chóng mặt)")
try:
    ctx3 = SymptomContext(raw_symptoms=["đi loạng choạng", "chóng mặt"])
    result3 = run(pipeline.diagnose(ctx3))
    nav3 = pipeline.to_navigator_output(result3)
    log(f"  is_emergency: {nav3['is_emergency']}")
    log(f"  reason      : {nav3.get('emergency_reason','')}")
    for c in nav3["candidates"]:
        log(f"    [{c['urgency']:10}] {c['disease_id']} {c['name_vn']} score={c['score']}")
    assert nav3["is_emergency"] is False, f"Expected False, got True"
    log("  RESULT: PASS")
except Exception as e:
    log(f"  RESULT: FAIL — {e}")
    traceback.print_exc()

# ── TEST 4: diagnose_enhanced wrapper ─────────────────────────────────────────
log("\n" + "="*60)
log("TEST 4: diagnose_enhanced() wrapper (sốt cao + cứng cổ)")
try:
    from missions_hub.medical_diagnostic_tool import diagnose_enhanced
    nav4 = run(diagnose_enhanced(["sốt cao", "cứng cổ"], {"age": 25, "sex": "nam"}))
    log(f"  is_emergency : {nav4['is_emergency']}")
    log(f"  candidates   : {len(nav4['candidates'])}")
    assert "candidates" in nav4
    assert "is_emergency" in nav4
    log("  RESULT: PASS")
except Exception as e:
    log(f"  RESULT: FAIL — {e}")
    traceback.print_exc()

# ── Write summary ──────────────────────────────────────────────────────────────
log("\n" + "="*60)
passes = sum(1 for r in results if "RESULT: PASS" in r)
fails  = sum(1 for r in results if "RESULT: FAIL" in r)
log(f"SUMMARY: {passes} passed, {fails} failed")

with open("_test_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("Results written to _test_results.txt")
