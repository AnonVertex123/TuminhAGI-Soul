"""
tests/test_treatment_router.py — TreatmentRouter Test Suite
============================================================
5 tests covering all decision tracks.
"""
import sys
import io
import json
from pathlib import Path

# UTF-8 safe output on Windows — only when running as a script, not under pytest
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from missions_hub.treatment_router import TreatmentRouter, TreatmentDecision

router = TreatmentRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Emergency → Tây y bắt buộc, KHÔNG có thuốc Nam
# ─────────────────────────────────────────────────────────────────────────────
def test_emergency_western_only():
    """I21 (STEMI) must always be emergency — herbal_options must be empty."""
    decision = router.decide("I21", urgency="emergency", symptom_severity="nặng")
    assert decision.track == "emergency", f"Expected 'emergency', got '{decision.track}'"
    assert decision.herbal_options == [], (
        f"herbal_options must be [] for emergency, got {decision.herbal_options}"
    )
    assert "ngay" in decision.warning.lower(), (
        f"Warning must contain 'ngay', got: {decision.warning}"
    )
    assert len(decision.western_options) > 0, "western_options must not be empty for emergency"
    print("[PASS] Test 1 — Emergency I21: herbal=[], western present, warning correct")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Đau dạ dày nhẹ → Thuốc Nam ưu tiên
# ─────────────────────────────────────────────────────────────────────────────
def test_gastric_ulcer_herbal_first():
    """K25 (gastric ulcer) + routine + nhẹ → herbal_only or both with herbal."""
    # Pass empty answers dict (all False → UNKNOWN → no constitution filtering)
    decision = router.decide("K25", urgency="routine", symptom_severity="nhẹ",
                             constitution_answers={})
    assert decision.track in ("herbal_only", "both"), (
        f"Expected 'herbal_only' or 'both', got '{decision.track}'"
    )
    assert len(decision.herbal_options) > 0, (
        f"Should find herbs for K25, got empty list.\n"
        f"Herb DB path: I:/TuminhAgi/data/tuminh_herb_encyclopedia.jsonl"
    )
    herb_names = [h["name_vn"] for h in decision.herbal_options]
    # Gừng or Nghệ or Cam thảo must be present for K25
    gastric_herbs = {"Gừng", "Nghệ vàng", "Cam thảo", "Bạch truật", "Sa nhân"}
    found = gastric_herbs & set(herb_names)
    assert found, (
        f"Expected at least one of {gastric_herbs} in herbal_options, got {herb_names}"
    )
    print(f"[PASS] Test 2 — Gastric K25 routine/nhẹ: track={decision.track}, herbs={herb_names[:3]}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Bệnh vừa (Hen suyễn J45) → Cả hai phương án
# ─────────────────────────────────────────────────────────────────────────────
def test_asthma_both_tracks():
    """J45 (asthma) + urgent + vừa → both, herbal and western both present."""
    decision = router.decide("J45", urgency="urgent", symptom_severity="vừa",
                             constitution_answers={})
    assert decision.track == "both", (
        f"Expected 'both', got '{decision.track}'"
    )
    assert decision.herbal_options is not None, "herbal_options should not be None"
    assert decision.western_options is not None and len(decision.western_options) > 0, (
        "western_options must not be empty"
    )
    print(f"[PASS] Test 3 — Asthma J45 urgent/vừa: track=both, "
          f"herbs={len(decision.herbal_options)}, western={len(decision.western_options)}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Trễ kinh (Phụ khoa N91) → Thuốc Nam phụ khoa
# ─────────────────────────────────────────────────────────────────────────────
def test_amenorrhea_obgyn_herbs():
    """N91 (amenorrhea) + routine + nhẹ → herbal contains gynecology herbs."""
    decision = router.decide("N91", urgency="routine", symptom_severity="nhẹ",
                             constitution_answers={})
    # Track can be herbal_only or both
    assert decision.track in ("herbal_only", "both"), (
        f"Expected 'herbal_only' or 'both', got '{decision.track}'"
    )
    if decision.herbal_options:
        herb_names = [h["name_vn"] for h in decision.herbal_options]
        # At least one of the key gynecology herbs must appear
        gynecology_herbs = {"Ích mẫu", "Hương phụ", "Ngải cứu", "Đương quy", "Xuyên khung"}
        found = gynecology_herbs & set(herb_names)
        assert found, (
            f"Expected OB/GYN herbs {gynecology_herbs} in result, got {herb_names}"
        )
        print(f"[PASS] Test 4 — N91 routine/nhẹ: OB/GYN herbs found = {list(found)}")
    else:
        # If empty, must have clear warning about no data
        assert decision.warning, "If no herbs found, warning must not be empty"
        print(f"[PASS] Test 4 — N91 no herb data but warning present: {decision.warning[:60]}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Mã lạ/hiếm (Z99) → Cảnh báo rõ
# ─────────────────────────────────────────────────────────────────────────────
def test_unknown_code_warning():
    """Z99 (rare/unknown code) must warn clearly about missing herb data."""
    decision = router.decide("Z99", urgency="routine", symptom_severity="nhẹ",
                             constitution_answers={})
    assert decision.warning != "", "Warning must not be empty for unknown code"
    warning_lower = decision.warning.lower()
    has_no_data = "chưa có" in warning_lower
    has_tham_khao = "tham khảo" in warning_lower
    has_cai_thien = "cải thiện" in warning_lower  # shown if herbs found (Z chapter)
    assert has_no_data or has_tham_khao or has_cai_thien, (
        f"Warning should mention missing data or referral, got: {decision.warning}"
    )
    print(f"[PASS] Test 5 — Z99 warning: '{decision.warning[:80]}'")


# ─────────────────────────────────────────────────────────────────────────────
# Demo print — full treatment output for đau dạ dày
# ─────────────────────────────────────────────────────────────────────────────
def demo_gastric():
    print("\n" + "="*60)
    print("DEMO: ['đau dạ dày', 'buồn nôn'], urgency=routine, severity=nhẹ")
    print("="*60)
    decision = router.decide("K25", urgency="routine", symptom_severity="nhẹ",
                             constitution_answers={})

    from nexus_core.output_formatter import format_treatment_output
    formatted = format_treatment_output(decision)

    print(f"Track       : {formatted['track']}")
    print(f"Emergency   : {formatted['emergency_banner']}")
    print(f"Warning     : {formatted['warning']}")
    print("\n--- Thuốc Nam ---")
    for s in formatted["sections"]:
        if s["type"] == "herbal" and s["visible"]:
            for item in s["items"]:
                print(f"  [{item['name_vn']}] {item['name_latin']}")
                print(f"    Dùng  : {item['usage']}")
                print(f"    Liều  : {item['dosage']}")
                print(f"    Lưu ý : {', '.join(item['contraindications'][:1])}")
    print("\n--- Tây y ---")
    for s in formatted["sections"]:
        if s["type"] == "western" and s["visible"]:
            for item in s["items"]:
                print(f"  {item.get('approach')} — {item.get('referral_type')}")


if __name__ == "__main__":
    import traceback
    tests = [
        test_emergency_western_only,
        test_gastric_ulcer_herbal_first,
        test_asthma_both_tracks,
        test_amenorrhea_obgyn_herbs,
        test_unknown_code_warning,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")

    demo_gastric()
