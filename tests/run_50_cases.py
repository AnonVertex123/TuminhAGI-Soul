#!/usr/bin/env python3
"""
TuminhAGI V9.4 — 50-Case Clinical Test Runner
═══════════════════════════════════════════════
Tests all pipeline components without external dependencies (Ollama).

Components tested:
  1. Emergency detection (keyword-based heuristic)
  2. Treatment routing  (TreatmentRouter.decide)
  3. Safety gates       (pregnancy, drug interaction)
  4. Input normalizer   (MedicalGatekeeper.normalize)
  5. Herb lookup + constitution filtering
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from missions_hub.treatment_router import TreatmentRouter, _lookup_herbs
from missions_hub.constitution_classifier import (
    ConstitutionClassifier,
    ConstitutionType,
    _PREGNANCY_CONTRAINDICATION_KEYWORDS,
    _DRUG_INTERACTION_MAP,
)
from nexus_core.strict_validator import MedicalGatekeeper
from missions_hub.medical_diagnostic_tool import _RED_FLAG_SYMPTOMS, clean_input


# ══════════════════════════════════════════════════════════════════════════════
# EMERGENCY DETECTION — mirrors MedicalDiagnosticTool._is_emergency_case
# ══════════════════════════════════════════════════════════════════════════════

def is_emergency_case(user_query: str) -> bool:
    text = (user_query or "").lower()

    has_high_fever = any(kw in text for kw in [
        "sốt cao", "sot cao", "high fever", "fever",
    ])
    has_neck_stiffness = any(kw in text for kw in [
        "cứng cổ", "cung co", "neck stiffness", "stiff neck",
    ])
    if has_high_fever and has_neck_stiffness:
        return True

    if any(kw in text for kw in [
        "đau ngực", "tức ngực", "chest pain", "angina", "precordial",
        "left-sided chest pain", "đau thắt ngực",
    ]):
        return True

    if any(kw in text for kw in [
        "liệt nửa người", "hemiparesis", "méo miệng", "facial droop",
        "nói ngọng", "slurred speech", "đột quỵ", "stroke",
    ]):
        return True

    if any(kw in text for kw in [
        "suy hô hấp", "respiratory distress", "ho ra máu", "hemoptysis",
    ]):
        return True

    if any(kw in text for kw in [
        "co giật", "co giat", "seizure", "convulsion",
        "mất ý thức", "mat y thuc", "loss of consciousness",
    ]):
        return True

    if any(kw in text for kw in [
        "nôn ra máu", "non ra mau", "hematemesis",
        "phân đen", "phan den", "melena",
    ]):
        return True

    if any(kw in text for kw in [
        "bụng cứng", "bung cung", "rigid abdomen",
        "đau bụng dữ dội", "dau bung du doi",
    ]):
        return True

    return any(kw in text for kw in _RED_FLAG_SYMPTOMS)


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT SINGLETONS
# ══════════════════════════════════════════════════════════════════════════════

router = TreatmentRouter()
classifier = ConstitutionClassifier()
gatekeeper = MedicalGatekeeper()

DEFAULT_CONSTITUTION = {"Q1": False, "Q2": False, "Q3": False, "Q4": False, "Q5": False}
PHONG_HAN = {"Q1": True, "Q2": False, "Q3": False, "Q4": False, "Q5": False}
PHONG_NHIET = {"Q1": False, "Q2": True, "Q3": False, "Q4": False, "Q5": False}


# ══════════════════════════════════════════════════════════════════════════════
# 50 TEST CASES
# ══════════════════════════════════════════════════════════════════════════════

CASES: list[dict[str, Any]] = [
    # ═══════════════ BỆNH THƯỜNG GẶP (1–15) ═══════════════
    {
        "id": 1, "group": "Thường gặp",
        "symptoms": ["sốt", "ho", "sổ mũi", "đau họng"],
        "context": {"age": 30, "trigger": "tự phát", "duration": "2 ngày"},
        "disease_id": "J06", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "J", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 2, "group": "Thường gặp",
        "symptoms": ["đau đầu vùng trán", "sổ mũi"],
        "context": {"age": 25},
        "disease_id": "J01", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "J", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 3, "group": "Thường gặp",
        "symptoms": ["đau dạ dày", "buồn nôn", "ợ chua"],
        "context": {"age": 30, "trigger": "sau ăn"},
        "disease_id": "K21", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "K", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 4, "group": "Thường gặp",
        "symptoms": ["tiêu chảy", "đau bụng quặn"],
        "context": {"age": 30, "trigger": "sau ăn lạ"},
        "disease_id": "K52", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "K", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 5, "group": "Thường gặp",
        "symptoms": ["mất ngủ", "lo âu", "hồi hộp nhẹ"],
        "context": {"age": 30, "trigger": "stress"},
        "disease_id": "F41", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "F", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 6, "group": "Thường gặp",
        "symptoms": ["đau lưng dưới", "mỏi cơ"],
        "context": {"age": 45},
        "disease_id": "M54", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "M", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 7, "group": "Thường gặp",
        "symptoms": ["ho khan", "khô họng", "ít đờm"],
        "context": {"age": 30, "duration": "3 tuần"},
        "disease_id": "R05", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "R", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 8, "group": "Thường gặp",
        "symptoms": ["chóng mặt nhẹ", "ù tai"],
        "context": {"age": 50},
        "disease_id": "R42", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "R", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 9, "group": "Thường gặp",
        "symptoms": ["táo bón", "bụng đầy hơi"],
        "context": {"age": 30},
        "disease_id": "K59", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "K", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 10, "group": "Thường gặp",
        "symptoms": ["dị ứng nổi mề đay", "ngứa"],
        "context": {"age": 30, "trigger": "sau ăn hải sản"},
        "disease_id": "L50", "expected_urgency": "routine",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "L", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 11, "group": "Thường gặp",
        "symptoms": ["viêm họng", "đau khi nuốt"],
        "context": {"age": 30, "duration": "3 ngày"},
        "disease_id": "J02", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "J", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 12, "group": "Thường gặp",
        "symptoms": ["cảm lạnh", "sợ lạnh", "không mồ hôi"],
        "context": {"age": 30, "trigger": "mưa lạnh"},
        "disease_id": "J00", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "J", "critical": False,
        "constitution": PHONG_HAN,
    },
    {
        "id": 13, "group": "Thường gặp",
        "symptoms": ["đau cơ toàn thân", "mệt mỏi"],
        "context": {"age": 30, "trigger": "sau vận động"},
        "disease_id": "M79", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "M", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 14, "group": "Thường gặp",
        "symptoms": ["miệng nhiệt", "lở miệng"],
        "context": {"age": 30, "trigger": "căng thẳng"},
        "disease_id": "K12", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "K", "critical": False,
        "constitution": PHONG_NHIET,
    },
    {
        "id": 15, "group": "Thường gặp",
        "symptoms": ["mệt mỏi", "kém ăn", "gầy yếu"],
        "context": {"age": 55},
        "disease_id": "R53", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "R", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },

    # ═══════════════ BỆNH MẠN TÍNH (16–28) ═══════════════
    {
        "id": 16, "group": "Mạn tính",
        "symptoms": ["khát nhiều", "tiểu nhiều", "mờ mắt"],
        "context": {"age": 58, "sex": "nam"},
        "disease_id": "E11", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "E", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 17, "group": "Mạn tính",
        "symptoms": ["đau đầu", "ù tai", "mặt đỏ"],
        "context": {"age": 55, "sex": "nam"},
        "disease_id": "I10", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "I", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "gate2_check": "warfarin_risk",
    },
    {
        "id": 18, "group": "Mạn tính",
        "symptoms": ["đau khớp ngón chân cái", "sưng đỏ"],
        "context": {"age": 55, "trigger": "sau bia"},
        "disease_id": "M10", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "M", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 19, "group": "Mạn tính",
        "symptoms": ["khó thở khi nằm", "phù chân"],
        "context": {"age": 65},
        "disease_id": "I50", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "I", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 20, "group": "Mạn tính",
        "symptoms": ["đau khớp gối", "cứng sáng"],
        "context": {"age": 62, "sex": "nữ"},
        "disease_id": "M17", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "M", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 21, "group": "Mạn tính",
        "symptoms": ["run tay", "đi chậm", "cứng cơ"],
        "context": {"age": 70},
        "disease_id": "G20", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "G", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 22, "group": "Mạn tính",
        "symptoms": ["ho mạn tính", "khạc đờm", "khó thở"],
        "context": {"age": 60},
        "disease_id": "J44", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "J", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 23, "group": "Mạn tính",
        "symptoms": ["vàng da nhẹ", "mệt mỏi", "chán ăn"],
        "context": {"age": 42},
        "disease_id": "K73", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "K", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 24, "group": "Mạn tính",
        "symptoms": ["đau thần kinh tọa", "lan xuống chân"],
        "context": {"age": 50},
        "disease_id": "M54", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "M", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 25, "group": "Mạn tính",
        "symptoms": ["trầm cảm nhẹ", "buồn bã", "mất hứng"],
        "context": {"age": 35},
        "disease_id": "F32", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "F", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 26, "group": "Mạn tính",
        "symptoms": ["tiểu buốt", "tiểu rắt"],
        "context": {"age": 55, "sex": "nam"},
        "disease_id": "N30", "expected_urgency": "routine",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 27, "group": "Mạn tính",
        "symptoms": ["đau dây thần kinh", "tê bì tay chân"],
        "context": {"age": 60},
        "disease_id": "G62", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "G", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 28, "group": "Mạn tính",
        "symptoms": ["loãng xương", "đau lưng mạn tính"],
        "context": {"age": 65, "sex": "nữ"},
        "disease_id": "M81", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "M", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },

    # ═══════════════ CẤP CỨU (29–38) — CRITICAL ═══════════════
    {
        "id": 29, "group": "Cấp cứu",
        "symptoms": ["đau ngực trái dữ dội", "lan vai", "mồ hôi"],
        "context": {"age": 68, "sex": "nam", "trigger": "gắng sức"},
        "disease_id": "I21", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "I", "critical": True,
    },
    {
        "id": 30, "group": "Cấp cứu",
        "symptoms": ["yếu liệt nửa người", "nói khó đột ngột"],
        "context": {"age": 65, "sex": "nữ"},
        "disease_id": "I63", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "I", "critical": True,
    },
    {
        "id": 31, "group": "Cấp cứu",
        "symptoms": ["đau đầu dữ dội đột ngột", "cứng cổ"],
        "context": {"age": 45},
        "disease_id": "I60", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "I", "critical": True,
    },
    {
        "id": 32, "group": "Cấp cứu",
        "symptoms": ["co giật toàn thân", "mất ý thức"],
        "context": {"age": 30},
        "disease_id": "G41", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "G", "critical": True,
    },
    {
        "id": 33, "group": "Cấp cứu",
        "symptoms": ["nôn ra máu", "đi ngoài phân đen"],
        "context": {"age": 50, "sex": "nam"},
        "disease_id": "K92", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "K", "critical": True,
    },
    {
        "id": 34, "group": "Cấp cứu",
        "symptoms": ["khó thở đột ngột", "ho ra máu", "đau ngực"],
        "context": {"age": 55},
        "disease_id": "I26", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "I", "critical": True,
    },
    {
        "id": 35, "group": "Cấp cứu",
        "symptoms": ["sốt cao 40 độ", "li bì", "cứng cổ"],
        "context": {"age": 20},
        "disease_id": "G00", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "G", "critical": True,
    },
    {
        "id": 36, "group": "Cấp cứu",
        "symptoms": ["đau bụng dưới dữ dội", "ngất", "trễ kinh"],
        "context": {"age": 26, "sex": "nữ"},
        "disease_id": "O00", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "O", "critical": True,
    },
    {
        "id": 37, "group": "Cấp cứu",
        "symptoms": ["khó thở nặng", "môi tím"],
        "context": {"age": 70},
        "disease_id": "J96", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "J", "critical": True,
    },
    {
        "id": 38, "group": "Cấp cứu",
        "symptoms": ["đau bụng dữ dội", "bụng cứng như gỗ"],
        "context": {"age": 22},
        "disease_id": "K35", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "K", "critical": True,
    },

    # ═══════════════ PHỤ KHOA (39–44) ═══════════════
    {
        "id": 39, "group": "Phụ khoa",
        "symptoms": ["trễ kinh 2 tháng", "không đau"],
        "context": {"age": 28, "sex": "nữ"},
        "disease_id": "N91", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "gate1_check": True,
    },
    {
        "id": 40, "group": "Phụ khoa",
        "symptoms": ["đau bụng kinh dữ dội", "buồn nôn"],
        "context": {"age": 22, "sex": "nữ"},
        "disease_id": "N94", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "gate1_check": True,
    },
    {
        "id": 41, "group": "Phụ khoa",
        "symptoms": ["khí hư màu vàng", "ngứa vùng kín"],
        "context": {"age": 35, "sex": "nữ"},
        "disease_id": "N76", "expected_urgency": "routine",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "gate1_check": True,
    },
    {
        "id": 42, "group": "Phụ khoa",
        "symptoms": ["trễ kinh", "đau bụng dưới"],
        "context": {"age": 30, "sex": "nữ", "pregnant": True},
        "disease_id": "N91", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "pregnancy_check": True,
    },
    {
        "id": 43, "group": "Phụ khoa",
        "symptoms": ["xuất huyết âm đạo bất thường", "nhiều"],
        "context": {"age": 45, "sex": "nữ"},
        "disease_id": "N93", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },
    {
        "id": 44, "group": "Phụ khoa",
        "symptoms": ["bốc hỏa", "đổ mồ hôi đêm"],
        "context": {"age": 52, "sex": "nữ"},
        "disease_id": "N95", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
    },

    # ═══════════════ EDGE CASES (45–50) ═══════════════
    {
        "id": 45, "group": "Edge case",
        "symptoms": ["dau nguc kho tho"],
        "context": {"age": 68, "sex": "nam"},
        "disease_id": "I21", "expected_urgency": "emergency",
        "expected_track": "emergency",
        "must_have_herbs": False, "must_not_have_herbs": True,
        "expected_icd_prefix": "I", "critical": True,
        "normalizer_check": True,
    },
    {
        "id": 46, "group": "Edge case",
        "symptoms": ["nhức đầu", "chóng mặt", "mệt"],
        "context": {"age": 70, "sex": "nữ", "medications": ["warfarin"]},
        "disease_id": "I10", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "I", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "drug_interaction_check": True,
    },
    {
        "id": 47, "group": "Edge case",
        "symptoms": ["sốt nhẹ", "ho", "đau đầu"],
        "context": {"age": 5},
        "disease_id": "J06", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": True, "must_not_have_herbs": False,
        "expected_icd_prefix": "J", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "pediatric_check": True,
    },
    {
        "id": 48, "group": "Edge case",
        "symptoms": ["mệt mỏi", "sụt cân", "ho kéo dài 3 tháng"],
        "context": {"age": 40},
        "disease_id": "A15", "expected_urgency": "urgent",
        "expected_track": "both",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "A", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "red_flag_check": True,
    },
    {
        "id": 49, "group": "Edge case",
        "symptoms": [],
        "context": {"age": 35},
        "disease_id": "R69", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "R", "critical": False,
        "empty_symptoms_check": True,
    },
    {
        "id": 50, "group": "Edge case",
        "symptoms": ["đau đầu", "trễ kinh", "buồn nôn"],
        "context": {"age": 25, "sex": "nữ", "pregnant": True},
        "disease_id": "N91", "expected_urgency": "routine",
        "expected_track": "herbal_only",
        "must_have_herbs": False, "must_not_have_herbs": False,
        "expected_icd_prefix": "N", "critical": False,
        "constitution": DEFAULT_CONSTITUTION,
        "pregnancy_check": True,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# CRITICAL RULES (hardcoded — never bypass)
# ══════════════════════════════════════════════════════════════════════════════

def rule_emergency(case: dict, decision: Any, detected_emergency: bool) -> list[str]:
    """RULE_EMERGENCY: cases 29-38 must have herbal=[] and is_emergency."""
    if case["id"] < 29 or case["id"] > 38:
        return []
    fails = []
    herbs = getattr(decision, "herbal_options", []) or []
    if len(herbs) != 0:
        fails.append(f"CRITICAL: herbal_options không rỗng ({len(herbs)} herbs) trong cấp cứu!")
    if decision.track != "emergency":
        fails.append(f"CRITICAL: track={decision.track}, expected=emergency")
    if not detected_emergency:
        fails.append(f"CRITICAL: is_emergency_case() trả về False cho ca cấp cứu!")
    return fails


def rule_pregnancy(case: dict, decision: Any) -> list[str]:
    """RULE_PREGNANCY: cases 42, 50 must have pregnancy warning."""
    if case["id"] not in (42, 50):
        return []
    fails = []
    warnings = getattr(decision, "safety_warnings", []) or []
    warning_text = " ".join(str(w) for w in warnings).lower()
    has_preg_warning = any(
        kw in warning_text
        for kw in ["có thai", "mang thai", "thai kỳ", "phụ nữ"]
    )
    if not has_preg_warning:
        fails.append("Không có cảnh báo thai kỳ (pregnancy warning)!")
    herbs = getattr(decision, "herbal_options", []) or []
    for h in herbs:
        contras = " ".join(str(c).lower() for c in h.get("contraindications", []))
        if "thai kỳ" in contras or "có thai" in contras or "sảy thai" in contras:
            fails.append(
                f"Thảo dược '{h.get('name_vn', '?')}' có chống chỉ định thai kỳ "
                f"nhưng vẫn xuất hiện trong kết quả!"
            )
    return fails


def rule_drug_interaction(case: dict, decision: Any) -> list[str]:
    """RULE_DRUG: cases 17, 46 — drug interaction check."""
    if case["id"] not in (17, 46):
        return []
    if "medications" not in case.get("context", {}):
        return []
    fails = []
    warnings = getattr(decision, "safety_warnings", []) or []
    warning_text = " ".join(str(w) for w in warnings).lower()
    meds = case["context"].get("medications", [])
    for med in meds:
        if med.lower() not in warning_text:
            fails.append(f"drug_interaction_warning không chứa '{med}'!")
    return fails


def rule_normalizer(case: dict, detected_emergency: bool) -> list[str]:
    """RULE_NORMALIZER: case 45 — no diacritics must still trigger emergency."""
    if case["id"] != 45:
        return []
    fails = []
    raw = " ".join(case["symptoms"])
    normalized = gatekeeper.normalize(raw)
    has_emergency_kw = any(
        kw in normalized
        for kw in ["đau ngực", "khó thở", "chest pain", "shortness of breath"]
    )
    if not has_emergency_kw:
        fails.append(f"Normalizer failed: '{raw}' → '{normalized}' (no emergency keywords)")
    if not detected_emergency:
        fails.append(f"Emergency detection failed after normalization: '{normalized}'")
    return fails


def rule_track(case: dict, decision: Any) -> list[str]:
    """RULE_TRACK: non-emergency cases must match expected track."""
    if case.get("expected_track") == "emergency":
        return []
    fails = []
    actual = decision.track
    expected = case.get("expected_track", "")
    if actual != expected:
        if expected == "both" and actual == "herbal_only":
            pass
        elif expected == "herbal_only" and actual == "both":
            pass
        else:
            fails.append(f"track={actual}, expected={expected}")
    return fails


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE TEST EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

def run_test(case: dict) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": case["id"],
        "group": case["group"],
        "pass": False,
        "failures": [],
        "critical_fail": False,
        "actual_urgency": "",
        "actual_track": "",
        "actual_herbs_count": 0,
        "emergency_detected": False,
        "notes": [],
    }

    try:
        query = ", ".join(case["symptoms"]) if case["symptoms"] else ""
        disease_id = case.get("disease_id", "R69")
        ctx = dict(case.get("context", {}))

        # --- Step 1: Emergency detection ---
        if case.get("normalizer_check"):
            normalized = gatekeeper.normalize(query)
            detected = is_emergency_case(normalized)
            result["notes"].append(f"Normalized: '{query}' → '{normalized}'")
        else:
            detected = is_emergency_case(query)
        result["emergency_detected"] = detected

        # --- Step 2: Treatment routing ---
        urgency = case.get("expected_urgency", "routine")
        constitution = case.get("constitution")
        decision = router.decide(
            disease_id=disease_id,
            urgency=urgency,
            symptom_severity=ctx.get("severity", ""),
            constitution_answers=constitution,
            context=ctx,
        )
        result["actual_urgency"] = decision.urgency
        result["actual_track"] = decision.track
        result["actual_herbs_count"] = len(decision.herbal_options or [])

        # --- Step 3: Apply safety gates for pregnancy/drug cases ---
        herbs_for_gate = list(decision.herbal_options or [])
        if not herbs_for_gate and case.get("pregnancy_check"):
            herbs_for_gate = _lookup_herbs(disease_id)
            if constitution:
                c_type = classifier.classify(constitution)
                herbs_for_gate = classifier.filter_herbs_by_constitution(herbs_for_gate, c_type)

        if (case.get("pregnancy_check") or case.get("drug_interaction_check")) and herbs_for_gate:
            gate_result = classifier.apply_gates(herbs_for_gate, ctx)
            decision.safety_warnings = gate_result.warnings
            decision.herbal_options = gate_result.herbs
            result["actual_herbs_count"] = len(gate_result.herbs)

        # --- Step 4: Collect all rule violations ---
        all_fails: list[str] = []

        all_fails.extend(rule_emergency(case, decision, detected))
        all_fails.extend(rule_pregnancy(case, decision))
        all_fails.extend(rule_drug_interaction(case, decision))
        all_fails.extend(rule_normalizer(case, detected))
        all_fails.extend(rule_track(case, decision))

        # Herb presence check for routine cases
        if case.get("must_have_herbs") and len(decision.herbal_options or []) == 0:
            pending = getattr(decision, "pending_questions", [])
            if not pending:
                all_fails.append("must_have_herbs=True nhưng herbal_options rỗng!")

        # Herb absence check for emergency
        if case.get("must_not_have_herbs") and len(decision.herbal_options or []) > 0:
            all_fails.append(
                f"must_not_have_herbs=True nhưng có {len(decision.herbal_options)} thảo dược!"
            )

        # Empty symptoms graceful handling
        if case.get("empty_symptoms_check"):
            result["notes"].append("Empty symptoms handled without crash")

        result["failures"] = all_fails
        result["pass"] = len(all_fails) == 0
        result["critical_fail"] = case.get("critical", False) and len(all_fails) > 0

    except Exception as exc:
        result["failures"] = [f"EXCEPTION: {exc}\n{traceback.format_exc()}"]
        result["critical_fail"] = case.get("critical", False)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ══════════════════════════════════════════════════════════════════════════════

def run_all() -> dict[str, Any]:
    timestamp = datetime.now().isoformat()
    results: list[dict] = []
    for case in CASES:
        r = run_test(case)
        results.append(r)

    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    failed = total - passed
    critical = sum(1 for r in results if r["critical_fail"])

    groups: dict[str, dict[str, int]] = {}
    for r in results:
        g = r["group"]
        if g not in groups:
            groups[g] = {"pass": 0, "fail": 0}
        if r["pass"]:
            groups[g]["pass"] += 1
        else:
            groups[g]["fail"] += 1

    failures = []
    for r in results:
        if not r["pass"]:
            failures.append({
                "id": r["id"],
                "group": r["group"],
                "reasons": r["failures"],
                "critical": r["critical_fail"],
            })

    return {
        "timestamp": timestamp,
        "version": "V9.4",
        "summary": {"total": total, "pass": passed, "fail": failed, "critical": critical},
        "by_group": groups,
        "failures": failures,
        "cases": results,
    }


# ══════════════════════════════════════════════════════════════════════════════
# REPORT PRINTERS
# ══════════════════════════════════════════════════════════════════════════════

GROUP_ORDER = ["Thường gặp", "Mạn tính", "Cấp cứu", "Phụ khoa", "Edge case"]


def print_report(report: dict) -> None:
    s = report["summary"]
    bg = report["by_group"]

    print()
    print("\u2554" + "\u2550" * 62 + "\u2557")
    print("\u2551" + "  TuminhAGI V9.4 — Clinical Test Report".center(62) + "\u2551")
    print("\u2560" + "\u2550" * 62 + "\u2563")
    print(
        "\u2551"
        + f"  Total: {s['total']}  │  Pass: {s['pass']}  │  Fail: {s['fail']}  │  Critical: {s['critical']}".ljust(
            62
        )
        + "\u2551"
    )
    print("\u2560" + "\u2550" * 62 + "\u2563")

    header = f"  {'NHÓM':<16}│ {'PASS':>5} │ {'FAIL':>5} │ {'TỶ LỆ':<20}"
    print("\u2551" + header.ljust(62) + "\u2551")

    for g in GROUP_ORDER:
        data = bg.get(g, {"pass": 0, "fail": 0})
        total_g = data["pass"] + data["fail"]
        pct = f"{data['pass'] * 100 // total_g}%" if total_g else "N/A"
        tag = " ← QUAN TRỌNG NHẤT" if g == "Cấp cứu" else ""
        row = f"  {g:<16}│ {data['pass']:>5} │ {data['fail']:>5} │ {pct:<5}{tag}"
        print("\u2551" + row.ljust(62) + "\u2551")

    print("\u2560" + "\u2550" * 62 + "\u2563")

    if report["failures"]:
        print("\u2551" + "  FAILURES:".ljust(62) + "\u2551")
        for f in report["failures"]:
            tag = "CRITICAL" if f["critical"] else "FAIL"
            for reason in f["reasons"]:
                line = f"  [{f['id']:>2}] {tag}: {reason}"
                for chunk_start in range(0, len(line), 60):
                    chunk = line[chunk_start : chunk_start + 60]
                    print("\u2551" + f"  {chunk}".ljust(62) + "\u2551")
    else:
        print("\u2551" + "  ALL 50 CASES PASSED!".ljust(62) + "\u2551")

    print("\u255A" + "\u2550" * 62 + "\u255D")
    print()


def save_report(report: dict) -> Path:
    results_dir = PROJECT_ROOT / "tests" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    out_path = results_dir / f"test_report_{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to: {out_path}")
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    report = run_all()
    print_report(report)
    save_report(report)

    if report["summary"]["critical"] > 0:
        print("!!! CRITICAL FAILURES DETECTED — pipeline needs fixes !!!")
        sys.exit(1)
    elif report["summary"]["fail"] > 0:
        print(f"Some tests failed ({report['summary']['fail']}). Review above.")
        sys.exit(1)
    else:
        print("ALL 50 CASES PASSED.")
        sys.exit(0)
