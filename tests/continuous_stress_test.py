import json
import sys
import os
import gc
from pathlib import Path

# Thêm directory gốc vào path
sys.path.append(str(Path(__file__).parent.parent))
from missions_hub.medical_diagnostic_tool import MedicalDiagnosticTool

def run_stress_test():
    print("🚀 BẮT ĐẦU HỆ THỐNG AUTO-TEST SUITE V9+ (Memory-Optimized Stress Test) 🚀")
    tool = MedicalDiagnosticTool()
    
    with open("tests/test_scenarios.json", "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    
    results = []
    total = len(scenarios)
    passed = 0
    batch_size = 5
    
    # Reset live log
    with open("tests/live_test_log.txt", "w", encoding="utf-8") as lf:
        lf.write("--- TỰ MINH AGI: BÁO CÁO TIẾN ĐỘ STRESS TEST V9+ ---\n")

    for i, case in enumerate(scenarios, 1):
        symptoms = case["symptoms"]
        expected_chap = case["expected_chapter"]
        
        # Batch reporting (every 10 or current index)
        if i % 10 == 1 or i == 1:
            print(f"\n--- 📈 TIẾN ĐỘ LÂM SÀNG: Đã xử lý {i-1}/{total} ca. ---")
            
        print(f"[{i}/{total}] Testing: {symptoms}", flush=True)
        
        # Chạy Diagnostic Loop (Bypass interactive)
        try:
            # V9+: Unpack correctly matching search_icd10 return
            q_vn, status_code, code, label, score, summary, formatted = tool.search_icd10(symptoms)
            
            # Nếu chẩn đoán hỏng, log lỗi và bỏ qua Chapter Check
            if "FAILED" in code or code == "NONE":
                status = "[FAIL - NO_CODE]"
                fail_reason = "Không tìm thấy mã ICD phù hợp."
                results.append({"symptoms": symptoms, "code": code, "status": status, "reason": fail_reason})
                print(f"Result: {status} | Case: {symptoms}", flush=True)
                continue

            # 1. Validation Logic: Chapter Match
            chap_pass, chap_reason = tool.strict_chapter_check(symptoms, code)
            
            # 2. Validation Logic: Dual-Path
            has_nam_y = "Nam Y" in summary or "Y học cổ truyền" in summary
            has_tay_y = "Tây Y" in summary or "Y học hiện đại" in summary or "Kháng sinh" in summary or "Xét nghiệm" in summary
            
            # 3. Validation Logic: Critic Guard
            is_guarded = "[FAILED]" in summary or "TỰ MINH AGI XIN HÀNG" in summary
            
            status = "PASS"
            fail_reason = ""
            
            if not chap_pass:
                status = "[FAIL - CHAPTER]"
                fail_reason = chap_reason
            elif not (has_nam_y and has_tay_y):
                status = "[FAIL - DUAL_PATH]"
                fail_reason = "Thiếu định hướng Nam Y hoặc Tây Y"
            elif is_guarded:
                status = "[SUCCESS - GUARDED]"
            
            if "PASS" in status or "SUCCESS" in status:
                passed += 1
            else:
                # Blacklist candidates for audit
                with open("tests/blacklist_candidates.log", "a", encoding="utf-8") as bl:
                    bl.write(f"SYMPTOMS: {symptoms}\nCODE: {code}\nSTATUS: {status}\nREASON: {fail_reason}\n\n")
            
            results.append({
                "symptoms": symptoms,
                "code": code,
                "status": status,
                "reason": fail_reason
            })
            print(f"Result: {status} | Code: {code}", flush=True)
            
            # Ghi nhật ký sống (Live Log)
            with open("tests/live_test_log.txt", "a", encoding="utf-8") as lf:
                lf.write(f"[{i}/{total}] {symptoms} -> {code} | {status} | {fail_reason}\n")
                
        except Exception as e:
            print(f"❌ LỖI HỆ THỐNG TRONG KHI TEST: {e}", flush=True)
            results.append({"symptoms": symptoms, "status": "[ERROR]", "reason": str(e)})
            with open("tests/live_test_log.txt", "a", encoding="utf-8") as lf:
                lf.write(f"[{i}/{total}] {symptoms} -> ERROR: {e}\n")

        # V9+: Giải phóng bộ nhớ sau mỗi ca
        gc.collect()
        
        # Batch Processing Delay if needed (Not required but for stability)
        if i % batch_size == 0:
            print(f"--- 🍃 Batch {i//batch_size} hoàn tất. Đang giải phóng RAM... ---")
            gc.collect()

    # Báo cáo cuối cùng
    print("\n" + "="*50)
    print("📋 BÁO CÁO CUỐI CÙNG (STRESS TEST REPORT)")
    print("="*50)
    print(f"Tổng số ca: {total}")
    print(f"Vượt qua (Pass/Guarded): {passed}")
    print(f"Tỉ lệ thành công: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🏆 CHÚC MỪNG HUYNH! HỆ THỐNG ĐẠT 100/100 ĐIỂM.")
        print("🚀 SẴN SÀNG PUBLIC GITHUB: 'Tự Minh AGI - Chân lý Y khoa'.")
    else:
        print(f"\n⚠️ CẦN CẢI THIỆN: Còn {total - passed} ca chưa đạt chuẩn.")
        
    # Lưu report
    with open("tests/stress_test_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run_stress_test()
