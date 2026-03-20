"""
missions_hub/knowledge_validator.py — Medical Knowledge Validator
=================================================================
Kiểm tra chất lượng trước khi merge vào knowledge base.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from missions_hub.knowledge_federation import KnowledgeContribution

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Kết quả validate contribution."""

    status: str  # ACCEPT | PENDING | REJECT | EXPERT
    reason: str | None = None


# ICD-10: letter + 2 digits, optional . + 1-2 digits
_ICD10_PATTERN = re.compile(r"^[A-Z]\d{2}(?:\.\d{1,2})?$", re.I)

# Valid outcomes
_VALID_OUTCOMES = frozenset({"recovered", "improved", "no_change", "worsened", "unknown"})


class MedicalKnowledgeValidator:
    """
    Kiểm tra chất lượng trước khi merge vào knowledge base.
    """

    CONFLICT_RESOLUTION_RULES = {
        1: "WHO / Bộ Y tế xác nhận",
        2: "Peer-reviewed research",
        3: "Bác sĩ YHCT xác nhận",
        4: "Nhiều báo cáo cộng đồng nhất quán",
        5: "Tự báo cáo đơn lẻ",
    }

    SAFETY_OVERRIDE = (
        "Nếu mâu thuẫn liên quan đến emergency/safety — "
        "LUÔN chọn option an toàn hơn "
        "bất kể evidence level. "
        "Sự sống > Độ chính xác thống kê."
    )

    def __init__(self, herb_encyclopedia_path: Path | None = None):
        self._herb_path = herb_encyclopedia_path or (
            Path(__file__).parent.parent / "data" / "tuminh_herb_encyclopedia.jsonl"
        )
        self._herb_names: frozenset[str] | None = None

    def _get_herb_names(self) -> frozenset[str]:
        """Load herb names from encyclopedia (cached)."""
        if self._herb_names is not None:
            return self._herb_names
        names: set[str] = set()
        if self._herb_path.exists():
            try:
                with open(self._herb_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            n = obj.get("name_vn", "")
                            if n:
                                names.add(str(n).strip())
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.warning("Could not load herb encyclopedia: %s", e)
        self._herb_names = frozenset(names)
        return self._herb_names

    def _is_valid_icd10(self, code: str) -> bool:
        """Check if string looks like valid ICD-10 code."""
        if not code or not isinstance(code, str):
            return False
        c = str(code).strip().upper()
        return bool(_ICD10_PATTERN.match(c))

    async def validate(self, contribution: KnowledgeContribution) -> ValidationResult:
        """
        Trả về:
        - ACCEPT: merge vào knowledge base
        - PENDING: cần thêm evidence
        - REJECT: có vấn đề nghiêm trọng
        - EXPERT: cần bác sĩ review
        """
        content = contribution.content or {}
        ctype = contribution.type

        # Minimum fields
        if ctype.value in ("symptom_pattern", "treatment_outcome", "herb_effectiveness"):
            symptoms = content.get("symptoms") or []
            diagnosis = content.get("diagnosis") or ""
            if not symptoms and not diagnosis:
                return ValidationResult("PENDING", "Thiếu triệu chứng hoặc chẩn đoán (ICD-10).")

            if diagnosis and not self._is_valid_icd10(str(diagnosis)):
                return ValidationResult("REJECT", f"Mã ICD-10 không hợp lệ: {diagnosis}")

        if ctype.value == "treatment_outcome":
            outcome = content.get("outcome") or ""
            if outcome and str(outcome).lower() not in _VALID_OUTCOMES:
                return ValidationResult("PENDING", f"Kết quả điều trị không hợp lệ. Dùng: {', '.join(_VALID_OUTCOMES)}")

        if ctype.value == "herb_effectiveness":
            herbs = content.get("herbs_used") or content.get("herb_used") or []
            if isinstance(herbs, str):
                herbs = [herbs] if herbs else []
            herb_names = self._get_herb_names()
            if herb_names:
                unknown = [h for h in herbs if str(h).strip() and str(h).strip() not in herb_names]
                if unknown:
                    return ValidationResult(
                        "PENDING",
                        f"Thuốc Nam chưa có trong bách khoa: {', '.join(unknown[:5])}. "
                        "Vui lòng dùng tên chuẩn (vd: Gừng, Nghệ vàng, Cam thảo).",
                    )

        if ctype.value == "red_flag_signal":
            return ValidationResult("EXPERT", "Cần bác sĩ YHCT review trước khi merge.")

        return ValidationResult("ACCEPT", None)
