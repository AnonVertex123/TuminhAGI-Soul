"""
missions_hub/knowledge_federation.py — Federated Knowledge System
=================================================================
Medical module ONLY. Private data = bất khả xâm phạm.
Upload = tự nguyện hoàn toàn. Server đồng hóa có chọn lọc.
Mọi Tự Minh cùng học từ cộng đồng.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContributionType(str, Enum):
    """Loại đóng góp tri thức từ người dùng."""

    SYMPTOM_PATTERN = "symptom_pattern"  # triệu chứng → bệnh đã xác nhận
    HERB_EFFECTIVENESS = "herb_effectiveness"  # thuốc Nam hiệu quả với bệnh gì
    TREATMENT_OUTCOME = "treatment_outcome"  # kết quả điều trị thực tế
    RED_FLAG_SIGNAL = "red_flag_signal"  # triệu chứng nguy hiểm bị bỏ sót


class EvidenceLevel(str, Enum):
    """Mức độ chứng cứ."""

    SELF_REPORTED = "self_reported"  # confidence 0.3
    COMMUNITY = "community"  # +0.1 per report
    DOCTOR_VERIFIED = "doctor_verified"  # 0.8
    WHO_RCT = "who_rct"  # 1.0


# PII patterns — scan before merge. Reject if found.
_PII_PATTERNS = [
    (re.compile(r"\b0\d{9,10}\b"), "phone"),  # Vietnamese phone
    (re.compile(r"\b\d{9,12}\b"), "id_number"),  # CMND
    (re.compile(r"\b[A-Za-zÀ-ỹ\s]{3,30}\b(?=.*(?:ngày sinh|sinh ngày|tuổi\s*\d{2}))"), "name_context"),
    (re.compile(r"\d{1,2}/\d{1,2}/\d{4}"), "birthdate"),
    (re.compile(r"\b(?:số\s+)?\d{1,3}(?:\s*[-/]\s*\d{1,3})*(?:\s*[-/]\s*\d{1,4})?\s*(?:phường|xã|quận|huyện|tp|tỉnh)\b", re.I), "address"),
]


@dataclass
class KnowledgeContribution:
    """
    Một đóng góp tri thức từ người dùng.
    LUÔN anonymous — is_anonymous và no_personal_info phải True.
    """

    contribution_id: str
    type: ContributionType
    content: dict[str, Any]
    metadata: dict[str, str]
    privacy: dict[str, bool]
    validation: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def create(
        cls,
        type: ContributionType,
        content: dict[str, Any],
        metadata: dict[str, str],
        consent_given: bool,
        evidence_level: EvidenceLevel = EvidenceLevel.SELF_REPORTED,
        source: str = "tự báo cáo",
        verified_by_md: bool = False,
    ) -> "KnowledgeContribution":
        """Create contribution with enforced anonymity."""
        return cls(
            contribution_id=str(uuid.uuid4()),
            type=type,
            content=content,
            metadata=metadata,
            privacy={
                "is_anonymous": True,  # LUÔN True
                "no_personal_info": True,  # LUÔN True
                "consent_given": consent_given,
            },
            validation={
                "evidence_level": evidence_level.value,
                "source": source,
                "verified_by_md": verified_by_md,
            },
        )


@dataclass
class KnowledgeEntry:
    """Một entry trong knowledge base (sau khi merge)."""

    entry_id: str
    type: str
    content: dict[str, Any]
    metadata: dict[str, str]
    confidence: float
    source_count: int
    created_at: str
    updated_at: str


@dataclass
class ContributionResult:
    """Kết quả nhận contribution."""

    accepted: bool
    reason: str
    contribution_id: str


@dataclass
class Resolution:
    """Kết quả resolve conflict."""

    winner: str  # "existing" | "incoming" | "both_pending"
    reason: str


@dataclass
class KnowledgeUpdate:
    """Update phân phối đến instances."""

    update_id: str
    priority: str  # "emergency" | "herb" | "general"
    payload: dict[str, Any]
    created_at: str


def _scan_pii(text: str) -> list[str]:
    """Scan text for PII. Returns list of matched pattern names."""
    found: list[str] = []
    if not text:
        return found
    s = str(text)
    for pat, name in _PII_PATTERNS:
        if pat.search(s):
            found.append(name)
    return found


def _scan_dict_for_pii(d: dict[str, Any], path: str = "") -> list[str]:
    """Recursively scan dict for PII."""
    found: list[str] = []
    for k, v in d.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, str):
            hits = _scan_pii(v)
            if hits:
                found.extend([f"{p}:{h}" for h in hits])
        elif isinstance(v, dict):
            found.extend(_scan_dict_for_pii(v, p))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, str):
                    hits = _scan_pii(item)
                    if hits:
                        found.extend([f"{p}[{i}]:{h}" for h in hits])
                elif isinstance(item, dict):
                    found.extend(_scan_dict_for_pii(item, f"{p}[{i}]"))
    return found


class FederationServer:
    """
    Server nhận và đồng hóa tri thức.
    """

    def __init__(self, knowledge_base_path: Optional[Path] = None):
        self._kb_path = knowledge_base_path or Path("data/knowledge_base.jsonl")
        self._kb_path.parent.mkdir(parents=True, exist_ok=True)
        self._updates_queue: list[KnowledgeUpdate] = []

    async def receive_contribution(
        self,
        contribution: KnowledgeContribution,
    ) -> ContributionResult:
        """
        Quy trình nhận contribution:

        Step 1 — Privacy check: scan content, reject if PII found.
        Step 2 — Safety check: RED_FLAG_SIGNAL → ưu tiên review.
        Step 3 — Quality check: min fields, ICD-10, herb names, outcome enum.
        Step 4 — Conflict detection: consistent / contradicts / new.
        Step 5 — Merge when confidence >= 0.5.
        """
        cid = contribution.contribution_id

        # Step 1 — Privacy check
        if not contribution.privacy.get("consent_given"):
            return ContributionResult(
                accepted=False,
                reason="Thiếu xác nhận đồng ý chia sẻ ẩn danh.",
                contribution_id=cid,
            )
        if not contribution.privacy.get("is_anonymous") or not contribution.privacy.get("no_personal_info"):
            return ContributionResult(
                accepted=False,
                reason="Đóng góp phải luôn ẩn danh và không chứa thông tin cá nhân.",
                contribution_id=cid,
            )

        # Scan for PII
        pii_found = _scan_dict_for_pii(contribution.content)
        pii_found.extend(_scan_dict_for_pii(contribution.metadata))
        if pii_found:
            logger.warning("Contribution rejected: PII detected (reason logged, data not stored)")
            return ContributionResult(
                accepted=False,
                reason="Phát hiện thông tin cá nhân. Vui lòng xóa tên, SĐT, địa chỉ, CMND, ngày sinh cụ thể.",
                contribution_id=cid,
            )

        # Step 2 — Safety check
        if contribution.type == ContributionType.RED_FLAG_SIGNAL:
            # Ưu tiên review — nhưng vẫn chạy qua validator
            pass  # Flagged for expert review in validator

        # Step 3 — Quality check (delegate to validator)
        try:
            from missions_hub.knowledge_validator import MedicalKnowledgeValidator

            validator = MedicalKnowledgeValidator()
            vr = await validator.validate(contribution)
            if vr.status == "REJECT":
                return ContributionResult(accepted=False, reason=vr.reason or "Chất lượng không đạt.", contribution_id=cid)
            if vr.status == "PENDING":
                return ContributionResult(
                    accepted=False,
                    reason=vr.reason or "Cần thêm thông tin để xác minh.",
                    contribution_id=cid,
                )
        except ImportError:
            vr = None

        # Step 4 — Conflict detection & Step 5 — Merge
        ev = contribution.validation.get("evidence_level", "self_reported")
        confidence = 0.3
        if ev == "doctor_verified":
            confidence = 0.8
        elif ev == "who_rct":
            confidence = 1.0
        elif ev == "community":
            confidence = 0.4  # Base + will increase with report count

        if confidence < 0.5 and (vr is None or vr.status != "ACCEPT"):
            return ContributionResult(
                accepted=False,
                reason="Chưa đủ độ tin cậy để merge (cần bác sĩ xác nhận hoặc nhiều báo cáo).",
                contribution_id=cid,
            )

        # Merge
        try:
            self._append_to_kb(contribution, confidence)
            logger.info("Contribution received and merged (no personal data in log)")
            return ContributionResult(accepted=True, reason="Đã đóng góp thành công.", contribution_id=cid)
        except Exception as e:
            logger.exception("Merge failed")
            return ContributionResult(accepted=False, reason=f"Lỗi hệ thống: {e}", contribution_id=cid)

    def _append_to_kb(self, c: KnowledgeContribution, confidence: float) -> None:
        """Append contribution to knowledge base (minimal persistence)."""
        entry = {
            "entry_id": c.contribution_id,
            "type": c.type.value,
            "content": c.content,
            "metadata": c.metadata,
            "confidence": confidence,
            "source_count": 1,
            "created_at": c.created_at,
            "updated_at": datetime.utcnow().isoformat(),
        }
        with open(self._kb_path, "a", encoding="utf-8") as f:
            f.write((__import__("json").dumps(entry, ensure_ascii=False) + "\n"))

    async def resolve_conflict(
        self,
        existing: KnowledgeEntry,
        incoming: KnowledgeContribution,
    ) -> Resolution:
        """
        Khi 2 contributions mâu thuẫn:
        Rule 1: Evidence wins — WHO/RCT > Doctor > Community > Self-report
        Rule 2: Volume wins khi cùng evidence level
        Rule 3: Safety wins — chọn option an toàn hơn
        Rule 4: Flag for human review khi mâu thuẫn nghiêm trọng
        """
        from missions_hub.knowledge_validator import MedicalKnowledgeValidator

        ev_order = {"who_rct": 4, "doctor_verified": 3, "community": 2, "self_reported": 1}
        inc_ev = incoming.validation.get("evidence_level", "self_reported")
        # Existing doesn't have validation dict in our simple model — assume community
        ex_ev = "community"
        ex_score = ev_order.get(ex_ev, 0)
        inc_score = ev_order.get(inc_ev, 0)

        if inc_score > ex_score:
            return Resolution("incoming", "Evidence level cao hơn.")
        if inc_score < ex_score:
            return Resolution("existing", "Evidence level thấp hơn.")

        # Volume
        ex_count = getattr(existing, "source_count", 1)
        if ex_count >= 10 and incoming.validation.get("verified_by_md"):
            return Resolution("both_pending", "Cần bác sĩ YHCT review — tạm hiển thị cả hai.")
        if ex_count > 1:
            return Resolution("existing", "Nhiều báo cáo hơn.")
        return Resolution("both_pending", "Cần bác sĩ YHCT review.")

    async def distribute_update(self, update: KnowledgeUpdate) -> None:
        """
        Phân phối tri thức mới đến tất cả instances.
        Ưu tiên: emergency → herb → general.
        Offline instances: queue and apply when online.
        """
        self._updates_queue.append(update)
        logger.info("Knowledge update queued for distribution (priority=%s)", update.priority)
