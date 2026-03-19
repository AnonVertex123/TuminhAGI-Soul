"""
tests/test_enhanced_pipeline.py
================================
3 integration tests for EnhancedDiagnosticPipeline V9.3.

Run with:
    python -m pytest tests/test_enhanced_pipeline.py -v
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pipeline():
    """Shared pipeline instance — loaded once per test session."""
    from missions_hub.enhanced_diagnostic_pipeline import EnhancedDiagnosticPipeline
    return EnhancedDiagnosticPipeline(embed_model="minilm")


def run(coro):
    """Helper: run async coroutine in sync test context."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Test 1: Cardiac emergency ─────────────────────────────────────────────────

def test_cardiac_emergency(pipeline):
    """
    'đau ngực trái' + 'khó thở' với trigger 'gắng sức' + age=68 + sex='nam'
    → top candidate MUST be urgency == 'emergency'
    """
    from missions_hub.enhanced_diagnostic_pipeline import SymptomContext

    ctx = SymptomContext(
        raw_symptoms=["đau ngực trái", "khó thở"],
        trigger="gắng sức",
        age=68,
        sex="nam",
    )
    result = run(pipeline.diagnose(ctx))
    nav = pipeline.to_navigator_output(result)

    assert nav["candidates"], "No candidates returned"
    top = nav["candidates"][0]

    assert top["urgency"] == "emergency", (
        f"Expected urgency='emergency', got '{top['urgency']}' "
        f"for disease '{top['name_vn']}' (score={top['score']}). "
        f"All candidates: {[(c['name_vn'], c['urgency']) for c in nav['candidates']]}"
    )
    print(f"\n[TEST 1 PASS] Top: {top['name_vn']} — urgency={top['urgency']}, score={top['score']}")


# ── Test 2: OBGYN domain guard ────────────────────────────────────────────────

def test_obgyn_no_epilepsy(pipeline):
    """
    'trễ kinh' + 'đau bụng dưới' (sex='nữ')
    → G40 (Epilepsy/Động kinh) must NOT appear in candidates.
    The SYNONYM_MAP maps 'trễ kinh' → amenorrhea, NOT seizure.
    """
    from missions_hub.enhanced_diagnostic_pipeline import SymptomContext

    ctx = SymptomContext(
        raw_symptoms=["trễ kinh", "đau bụng dưới"],
        sex="nữ",
    )
    result = run(pipeline.diagnose(ctx))
    nav = pipeline.to_navigator_output(result)

    disease_ids = [c["disease_id"] for c in nav["candidates"]]
    assert "G40" not in disease_ids, (
        f"OBGYN guard FAILED — G40 (Epilepsy) appeared in candidates: {disease_ids}. "
        "Check SYNONYM_MAP for 'trễ kinh' and domain filtering."
    )
    print(f"\n[TEST 2 PASS] Candidates: {[(c['disease_id'], c['name_vn']) for c in nav['candidates']]}")
    print("  G40 correctly excluded.")


# ── Test 3: Gait ataxia — not emergency ───────────────────────────────────────

def test_gait_ataxia_not_emergency(pipeline):
    """
    'đi loạng choạng' + 'chóng mặt'
    → is_emergency must be False (ataxia is not an immediate life threat
      in the absence of other red flags).
    """
    from missions_hub.enhanced_diagnostic_pipeline import SymptomContext

    ctx = SymptomContext(
        raw_symptoms=["đi loạng choạng", "chóng mặt"],
    )
    result = run(pipeline.diagnose(ctx))
    nav = pipeline.to_navigator_output(result)

    assert nav["is_emergency"] is False, (
        f"Expected is_emergency=False for ataxia+dizziness. "
        f"Got True. Reason: {nav.get('emergency_reason')}. "
        f"Candidates: {[(c['disease_id'], c['urgency']) for c in nav['candidates']]}"
    )
    print(f"\n[TEST 3 PASS] is_emergency=False for gait ataxia.")
    print(f"  Candidates: {[(c['disease_id'], c['name_vn'], c['urgency']) for c in nav['candidates']]}")


# ── Test 4: diagnose_enhanced wrapper ────────────────────────────────────────

def test_diagnose_enhanced_wrapper():
    """
    Verify the module-level diagnose_enhanced() function works end-to-end.
    """
    from missions_hub.medical_diagnostic_tool import diagnose_enhanced

    result = run(diagnose_enhanced(
        symptoms=["sốt cao", "cứng cổ"],
        context_dict={"age": 25, "sex": "nam"},
    ))

    assert "candidates" in result, f"Missing 'candidates' key: {result}"
    assert "is_emergency" in result, f"Missing 'is_emergency' key: {result}"
    assert isinstance(result["candidates"], list), "candidates must be a list"
    print(f"\n[TEST 4 PASS] diagnose_enhanced wrapper OK. "
          f"is_emergency={result['is_emergency']}, "
          f"candidates={len(result['candidates'])}")
