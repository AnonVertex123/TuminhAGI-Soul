import sys
import json
import time
from pathlib import Path

# Thêm path để import các module từ nexus_core
sys.path.append(str(Path(__file__).parent.parent))
from nexus_core.eternal_memory import EternalMemoryManager

class MedicalFoundationLoader:
    """
    Chief Medical Informatics Architect's Module
    Tích hợp dữ liệu y tế gốc và thiết lập Emergency Mode cho TuminhAGI.
    """
    def __init__(self):
        self.eternal = EternalMemoryManager()
        self.topic_tag = "[TOPIC: GENERAL_MEDICINE]"
        self.emergency_tag = "[EMERGENCY_ACLS_VITAL]"

    def load_drug_bank(self, sample_data=None):
        """
        Nạp dữ liệu Dược lý (Cơ chế, Liều lượng, Tương tác).
        """
        print(f"💊 Loading DrugBank Extended Pipeline...")
        # Giả lập dữ liệu nếu không có file thực tế
        data = sample_data or [
            {
                "drug": "Metformin",
		"mechanism": "Activation of AMP-activated protein kinase (AMPK)",
                "dosage": "500mg to 2000mg daily",
                "interactions": "Contrast media, Alcohol",
                "indications": "Type 2 Diabetes Mellitus"
            },
            {
                "drug": "Lisinopril",
                "mechanism": "ACE inhibitor",
                "dosage": "10mg to 40mg daily",
                "interactions": "Potassium supplements, NSAIDs",
                "indications": "Hypertension, Heart failure"
            }
        ]
        
        for item in data:
            content = (
                f"{self.topic_tag} DRUG: {item['drug']}\n"
                f"Mechanism: {item['mechanism']}\n"
                f"Dosage: {item['dosage']}\n"
                f"Interactions: {item['interactions']}\n"
                f"Indications: {item['indications']}"
            )
            # Lưu vào Eternal Memory với điểm số cao cho độ tin cậy y tế
            self.eternal.add_memory(content, is_vital=False, human_score=90)
        print(f"✅ DrugBank data synchronized.")

    def load_icd10_mapping(self, sample_data=None):
        """
        Ánh xạ ICD-10 cho Bệnh lý & Triệu chứng.
        """
        print(f"📋 Indexing ICD-10 Pathology Mapping...")
        data = sample_data or [
            {"code": "I10", "description": "Essential (primary) hypertension"},
            {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications"},
            {"code": "J06.9", "description": "Acute upper respiratory infection, unspecified"}
        ]
        
        for item in data:
            content = f"{self.topic_tag} ICD-10 CODE: {item['code']} - {item['description']}"
            self.eternal.add_memory(content, is_vital=False, human_score=95)
        print(f"✅ ICD-10 Mapping integrated.")

    def load_merck_manual_professional(self, sample_data=None):
        """
        Nạp kiến thức tóm tắt từ Merck Manual Professional.
        """
        print(f"📚 Parsing Merck Manual Clinical Guidelines...")
        data = sample_data or [
            {
                "topic": "Heart Failure",
                "symptoms": "Dyspnea, Fatigue, Fluid retention",
                "diagnosis": "Echocardiography, BNP levels",
                "treatment": "ACE inhibitors, beta-blockers, diuretics"
            }
        ]
        
        for item in data:
            content = (
                f"{self.topic_tag} CLINICAL GUIDE: {item['topic']}\n"
                f"Symptoms: {item['symptoms']}\n"
                f"Diagnosis: {item['diagnosis']}\n"
                f"Treatment: {item['treatment']}"
            )
            self.eternal.add_memory(content, is_vital=False, human_score=92)
        print(f"✅ Merck Manual guidelines processed.")

    def setup_emergency_mode(self):
        """
        Thiết lập Emergency Mode (Phác đồ ACLS/Sơ cấp cứu độ ưu tiên cao nhất).
        Các bản ghi này sẽ được đánh dấu VITAL để bypass suy luận.
        """
        print(f"🚨 ACTIVATING EMERGENCY MODE: ACLS/First Aid Protocols...")
        protocols = [
            {
                "situation": "Cardiac Arrest (Ngừng tim)",
                "action": "1. Call 115. 2. Start CPR (100-120 bpm). 3. Use AED as soon as available.",
                "acls": "High-quality CPR, Oxygen, Attach monitor/defibrillator."
            },
            {
                "situation": "Anaphylaxis (Sốc phản vệ)",
                "action": "1. Administer Epinephrine 0.3mg IM. 2. Call Emergency. 3. Monitor airway.",
                "acls": "IM Epinephrine (1:1000), Supine position, High-flow oxygen."
            },
            {
                "situation": "Severe Bleeding (Chảy máu nghiêm trọng)",
                "action": "1. Apply direct pressure. 2. Use tourniquet if limb bleeding is life-threatening.",
                "acls": "Direct pressure, Pressure dressing, Tourniquet application."
            }
        ]
        
        for p in protocols:
            content = (
                f"{self.emergency_tag} SITUATION: {p['situation']}\n"
                f"IMMEDIATE ACTION: {p['action']}\n"
                f"ACLS PROTOCOL: {p['acls']}\n"
                f"**BYPASS REASONING AND REPLY IMMEDIATELY**"
            )
            # Đặt is_vital=True và human_score=100 để Orchestrator Step 0 bắt được ngay lập tức
            self.eternal.add_memory(content, is_vital=True, human_score=100)
        
        print(f"✅ Emergency protocols locked and loaded into VITAL layer.")

if __name__ == "__main__":
    loader = MedicalFoundationLoader()
    loader.load_drug_bank()
    loader.load_icd10_mapping()
    loader.load_merck_manual_professional()
    loader.setup_emergency_mode()
    print("\n[MEDICAL FOUNDATION] All systems nominal. Emergency VITAL layer active.")
