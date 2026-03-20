"""
tests/test_constitution_safety.py — Constitution & Safety Gate Tests
=====================================================================
8 safety-focused tests for TuminhAGI V9.4 constitution classifier.

Safety rules tested:
  1. Phong nhiệt excludes ôn/nhiệt herbs
  2. Phong hàn excludes hàn/lương herbs
  3. Pregnancy gate removes unsafe herbs
  4. Drug interaction gate warns
  5. UNKNOWN constitution returns safe herbs + YHCT note
  6. Duration cap always present in decision
  7. Forbidden language gate auto-corrects output
  8. No answers → pending_questions returned, no herbs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from missions_hub.constitution_classifier import (
    ConstitutionClassifier,
    ConstitutionType,
    QUESTIONS,
    DURATION_CAP,
)
from missions_hub.treatment_router import TreatmentRouter
from nexus_core.output_formatter import format_treatment_output, _language_guard


clf    = ConstitutionClassifier()
router = TreatmentRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a minimal herb dict
# ─────────────────────────────────────────────────────────────────────────────
def _herb(name: str, tinh: str, contraindications: list | None = None) -> dict:
    return {
        "herb_id": f"TEST_{name}",
        "name_vn": name,
        "tinh": tinh,
        "safety_level": "safe",
        "contraindications": contraindications or [],
        "usage": "Sắc uống",
        "dosage": "10g/ngày",
        "evidence_level": "medium",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Phong nhiệt excludes warming (ôn/nhiệt) herbs
# ─────────────────────────────────────────────────────────────────────────────
def test_phong_nhiet_excludes_warming():
    all_herbs = [
        _herb("Gừng",        "ôn"),
        _herb("Tía tô",      "ôn"),
        _herb("Đan sâm",     "lương"),
        _herb("Câu đằng",    "lương"),
        _herb("Phục linh",   "bình"),
    ]
    result = clf.filter_herbs_by_constitution(all_herbs, ConstitutionType.PHONG_NHIET)
    result_names = {h["name_vn"] for h in result}
    # Warming herbs must be excluded
    assert "Gừng"  not in result_names, "Gừng (ôn) must be excluded for Phong nhiệt"
    assert "Tía tô" not in result_names, "Tía tô (ôn) must be excluded for Phong nhiệt"
    # Cool/neutral herbs must remain
    assert "Đan sâm"  in result_names, "Đan sâm (lương) must remain for Phong nhiệt"
    assert "Phục linh" in result_names, "Phục linh (bình) must remain for Phong nhiệt"
    # Verify no ôn/nhiệt tinh in result
    bad_tinhs = {"ôn", "nhiệt"}
    for h in result:
        assert h["tinh"] not in bad_tinhs, (
            f"Herb {h['name_vn']} has tinh={h['tinh']} — should be excluded for Phong nhiệt"
        )
    print(f"[PASS] Test 1 — Phong nhiệt: excluded ôn/nhiệt, kept {[h['name_vn'] for h in result]}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Phong hàn excludes cooling (hàn/lương) herbs
# ─────────────────────────────────────────────────────────────────────────────
def test_phong_han_excludes_cooling():
    all_herbs = [
        _herb("Kim ngân hoa", "lương"),
        _herb("Bồ công anh",  "hàn"),
        _herb("Gừng",         "ôn"),
        _herb("Kinh giới",    "ôn"),
        _herb("Phục linh",    "bình"),
    ]
    result = clf.filter_herbs_by_constitution(all_herbs, ConstitutionType.PHONG_HAN)
    result_names = {h["name_vn"] for h in result}
    # Cool/cold herbs must be excluded
    assert "Kim ngân hoa" not in result_names, "Kim ngân hoa (lương) must be excluded for Phong hàn"
    assert "Bồ công anh"  not in result_names, "Bồ công anh (hàn) must be excluded for Phong hàn"
    # Warm/neutral must remain
    assert "Gừng"     in result_names
    assert "Kinh giới" in result_names
    assert "Phục linh" in result_names
    # Verify no hàn/lương in result
    bad_tinhs = {"hàn", "lương"}
    for h in result:
        assert h["tinh"] not in bad_tinhs, (
            f"Herb {h['name_vn']} has tinh={h['tinh']} — should be excluded for Phong hàn"
        )
    print(f"[PASS] Test 2 — Phong hàn: excluded hàn/lương, kept {[h['name_vn'] for h in result]}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Pregnancy gate removes herbs with pregnancy risk
# ─────────────────────────────────────────────────────────────────────────────
def test_pregnancy_gate_removes_unsafe():
    herbs_with_risk = [
        _herb("Ích mẫu",    "lương", ["KHÔNG DÙNG KHI CÓ THAI (gây co tử cung, sảy thai)"]),
        _herb("Ngải cứu",   "ôn",    ["Không dùng liều cao khi có thai"]),
        _herb("Phục linh",  "bình",  ["Không dùng khi tiểu nhiều do thận hư"]),
        _herb("Đại táo",    "ôn",    ["Thận trọng với đái tháo đường"]),
    ]
    ctx = {"có thai": True}
    gate_result = clf.apply_gates(herbs_with_risk, ctx)

    remaining_names = [h["name_vn"] for h in gate_result.herbs]
    # Pregnancy-risk herbs must be removed
    assert "Ích mẫu"  not in remaining_names, "Ích mẫu must be removed (sảy thai risk)"
    assert "Ngải cứu" not in remaining_names, "Ngải cứu must be removed (thai risk)"
    # Safe herbs must remain
    assert "Phục linh" in remaining_names
    assert "Đại táo"   in remaining_names

    # Warning must mention pregnancy
    assert gate_result.warnings, "Warnings must not be empty for pregnancy context"
    combined = " ".join(gate_result.warnings).lower()
    assert "có thai" in combined or "thai" in combined, (
        f"Warning must mention pregnancy, got: {gate_result.warnings}"
    )
    print(f"[PASS] Test 3 — Pregnancy gate: removed {set(h['name_vn'] for h in herbs_with_risk if h['name_vn'] not in remaining_names)}, warnings present")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Drug interaction gate warns about Đan sâm + warfarin
# ─────────────────────────────────────────────────────────────────────────────
def test_drug_interaction_warning():
    dan_sam = {
        "herb_id": "H015",
        "name_vn": "Đan sâm",
        "tinh": "lương",
        "safety_level": "caution",
        "contraindications": ["Không dùng cùng warfarin"],
        "usage": "Sắc uống",
        "dosage": "9–15 g/ngày",
        "evidence_level": "high",
    }
    ctx = {"medications": ["warfarin"]}
    gate_result = clf.apply_gates([dan_sam], ctx)

    assert gate_result.warnings, "Must produce warnings for warfarin + Đan sâm"
    combined = " ".join(gate_result.warnings).lower()
    assert "warfarin" in combined or "tương tác" in combined, (
        f"Warning must mention warfarin interaction, got: {gate_result.warnings}"
    )
    # Herb should still be present (we warn, not remove)
    assert len(gate_result.herbs) == 1
    herb = gate_result.herbs[0]
    assert "interaction_warning" in herb, "interaction_warning field must be injected into herb"
    print(f"[PASS] Test 4 — Drug interaction: Đan sâm + warfarin warns correctly: '{gate_result.warnings[0][:60]}'")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — UNKNOWN constitution returns all herbs, safe-first, with YHCT note
# ─────────────────────────────────────────────────────────────────────────────
def test_unknown_constitution_returns_all_safe_herbs():
    all_herbs = [
        _herb("Herb A", "ôn"),
        _herb("Herb B", "hàn"),
        _herb("Herb C", "bình"),
        _herb("Herb D", "lương"),
    ]
    result = clf.filter_herbs_by_constitution(all_herbs, ConstitutionType.UNKNOWN)
    assert len(result) == len(all_herbs), (
        f"UNKNOWN should return all herbs, got {len(result)} instead of {len(all_herbs)}"
    )
    # Safe herbs first
    safe_herbs = [h for h in result if h.get("safety_level") == "safe"]
    assert len(safe_herbs) > 0, "UNKNOWN filter must return some safe herbs"

    # Constitution note must reference YHCT doctor
    note = clf.constitution_note(ConstitutionType.UNKNOWN).lower()
    assert "thầy thuốc" in note or "yhct" in note, (
        f"UNKNOWN note must reference YHCT doctor, got: {note}"
    )
    print(f"[PASS] Test 5 — UNKNOWN: all {len(result)} herbs returned, YHCT note present")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Duration cap always present in TreatmentDecision
# ─────────────────────────────────────────────────────────────────────────────
def test_duration_cap_always_present():
    answers = {"Q1": False, "Q2": False, "Q3": False, "Q4": False, "Q5": False}
    decision = router.decide("K25", "routine", "nhẹ", constitution_answers=answers)
    formatted = format_treatment_output(decision)

    duration_cap = formatted.get("duration_cap", "")
    assert duration_cap, "duration_cap must not be empty"
    assert "tuần" in duration_cap or "tuan" in duration_cap.replace("ầ", "a"), (
        f"duration_cap must mention 'tuần', got: {duration_cap}"
    )
    # Also check in warning or the actual DURATION_CAP constant
    all_text = " ".join([
        duration_cap,
        formatted.get("warning", ""),
        decision.warning,
    ])
    assert "tuần" in all_text or "khám bác sĩ" in all_text.lower(), (
        f"Duration cap must mention 'tuần' or 'khám bác sĩ', got all_text={all_text[:120]}"
    )
    print(f"[PASS] Test 6 — Duration cap: '{duration_cap[:60]}'")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — Language guard auto-corrects forbidden phrases
# ─────────────────────────────────────────────────────────────────────────────
def test_forbidden_language_auto_corrected():
    bad_texts = [
        "Bạn bị viêm dạ dày, điều trị bằng Nghệ vàng.",
        "Chẩn đoán là viêm phổi.",
        "Chắc chắn là bệnh tim.",
        "Kết luận rằng bạn mắc bệnh cao huyết áp.",
    ]
    for bad in bad_texts:
        corrected = _language_guard(bad)
        # Must not contain forbidden phrases after correction
        lower = corrected.lower()
        assert "bạn bị " not in lower,     f"'bạn bị' still present: {corrected}"
        assert "điều trị bằng" not in lower, f"'điều trị bằng' still present: {corrected}"
        assert "chẩn đoán là" not in lower, f"'chẩn đoán là' still present: {corrected}"
        assert "chắc chắn" not in lower,   f"'chắc chắn' still present: {corrected}"
        # Must have safe replacement
        assert corrected != bad, f"Language guard must have changed: {bad}"

    # Test via format_treatment_output round-trip
    from missions_hub.treatment_router import TreatmentDecision
    bad_decision = TreatmentDecision(
        track="herbal_only",
        urgency="routine",
        warning="Bạn bị đau dạ dày — điều trị bằng Gừng.",
    )
    formatted = format_treatment_output(bad_decision)
    warning_out = formatted.get("warning", "").lower()
    assert "bạn bị " not in warning_out, (
        f"Language guard must correct warning in formatted output, got: {formatted['warning']}"
    )
    print("[PASS] Test 7 — Language guard: all forbidden phrases auto-corrected")


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — No answers → pending_questions returned, herbal_options empty
# ─────────────────────────────────────────────────────────────────────────────
def test_no_answers_returns_questions_not_herbs():
    decision = router.decide("K25", "routine", "nhẹ", constitution_answers=None)
    assert decision.herbal_options == [], (
        f"herbal_options must be [] when no constitution answers, got {decision.herbal_options}"
    )
    assert decision.pending_questions is not None and len(decision.pending_questions) == 5, (
        f"Must return 5 pending questions, got: {decision.pending_questions}"
    )
    # Verify question keys Q1..Q5
    keys = {q["key"] for q in decision.pending_questions}
    assert keys == {"Q1", "Q2", "Q3", "Q4", "Q5"}, (
        f"Questions must have keys Q1..Q5, got {keys}"
    )
    print(f"[PASS] Test 8 — No answers: herbal=[], {len(decision.pending_questions)} questions returned")


# ─────────────────────────────────────────────────────────────────────────────
# DEMO — Full output for đau đầu, Q1=yes (sợ lạnh → Phong hàn)
# ─────────────────────────────────────────────────────────────────────────────
def demo_headache_phong_han():
    print("\n" + "="*65)
    print("DEMO: ['đau đầu'], answers={Q1:yes, Q2:no, Q3:no, Q4:no, Q5:no}")
    print("="*65)

    answers = {"Q1": True, "Q2": False, "Q3": False, "Q4": False, "Q5": False}
    constitution = clf.classify(answers)
    print(f"Constitution  : {constitution.value}")
    print(f"Note          : {clf.constitution_note(constitution)}")

    # G43 = Migraine, nearest to đau đầu
    decision = router.decide(
        "G43", urgency="routine", symptom_severity="nhẹ",
        constitution_answers=answers,
    )
    formatted = format_treatment_output(decision)

    print(f"Track         : {formatted['track']}")
    print(f"Emergency     : {formatted['emergency_banner']}")
    print(f"Constitution  : {formatted['constitution']['type']}")
    print(f"Duration cap  : {formatted['duration_cap']}")
    print(f"Warning       : {formatted['warning']}")
    print(f"Safety warns  : {formatted['safety_warnings']}")

    herbal_sec = next((s for s in formatted["sections"] if s["type"] == "herbal"), None)
    if herbal_sec and herbal_sec.get("visible"):
        print("\n--- Thuốc Nam gợi ý (đã lọc cho Phong hàn) ---")
        for item in herbal_sec["items"]:
            print(f"  [{item['name_vn']}] tinh={item['tinh']} ({item.get('tinh_label','')})")
            print(f"    Dùng     : {item['usage']}")
            print(f"    Liều     : {item['dosage']}")
            print(f"    Bằng chứng: {item['evidence']}")
            contras = item.get('contraindications', [])
            if contras:
                print(f"    Lưu ý  : {contras[0]}")
    else:
        print("\n--- Không có Thuốc Nam phù hợp cho G43 Phong hàn ---")

    print(f"\n{'─'*50}")
    print(f"Disclaimer: {formatted['disclaimer']}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import io, traceback
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    tests = [
        test_phong_nhiet_excludes_warming,
        test_phong_han_excludes_cooling,
        test_pregnancy_gate_removes_unsafe,
        test_drug_interaction_warning,
        test_unknown_constitution_returns_all_safe_herbs,
        test_duration_cap_always_present,
        test_forbidden_language_auto_corrected,
        test_no_answers_returns_questions_not_herbs,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed / {len(tests)} tests")
    demo_headache_phong_han()
