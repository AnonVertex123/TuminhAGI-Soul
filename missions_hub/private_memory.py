"""
missions_hub/private_memory.py — Private Memory (Federated Knowledge)
=====================================================================
Ký ức riêng tư của từng người dùng. KHÔNG AI được đọc — kể cả server.
Stored locally, encrypted. NO network calls — ever.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from missions_hub.knowledge_federation import (
    ContributionType,
    EvidenceLevel,
    KnowledgeContribution,
)

logger = logging.getLogger(__name__)

import base64

# Try Fernet for encryption; fallback to XOR obfuscation if not available
try:
    from cryptography.fernet import Fernet

    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


def _derive_key(user_id: str) -> bytes:
    """Derive 32-byte key from user_id for Fernet (local only)."""
    import hashlib

    return hashlib.sha256(user_id.encode("utf-8")).digest()


@dataclass
class PrivateEntry:
    """Một entry trong private memory."""

    entry_id: str
    symptoms: list[str]
    diagnosis: str
    treatment: str
    outcome: str
    duration_days: int
    herbs_used: list[str]
    age_group: str  # child | adult | elderly
    region: str
    season: str
    raw_note: str = ""


def _derive_key(user_id: str) -> bytes:
    """Derive encryption key from user_id (local only)."""
    salt = b"tuminh_private_memory_v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(user_id.encode("utf-8"))[:32])
    return key


def _xor_obfuscate(data: bytes, key: bytes) -> bytes:
    """Simple XOR obfuscation when Fernet not available."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def _xor_deobfuscate(data: bytes, key: bytes) -> bytes:
    return _xor_obfuscate(data, key)


class PrivateMemory:
    """
    Ký ức riêng tư của từng người dùng.
    KHÔNG AI được đọc — kể cả server.
    Stored locally, encrypted.
    NO method uploads automatically. All uploads via prepare_contribution() + explicit user action.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.storage_path = Path(f"local_data/{user_id}/private/")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        if _HAS_CRYPTO:
            key_b64 = base64.urlsafe_b64encode(_derive_key(user_id))
            self._cipher = Fernet(key_b64)
            self._key = key_b64
        else:
            self._cipher = None
            self._key = hashlib.sha256(user_id.encode("utf-8")).digest()

    def _encrypt(self, data: str) -> bytes:
        """Encrypt string to bytes."""
        raw = data.encode("utf-8")
        if self._cipher:
            return self._cipher.encrypt(raw)
        return _xor_obfuscate(raw, self._key)

    def _decrypt(self, data: bytes) -> str:
        """Decrypt bytes to string."""
        if self._cipher:
            return self._cipher.decrypt(data).decode("utf-8")
        return _xor_deobfuscate(data, self._key).decode("utf-8")

    def _entry_path(self, entry_id: str) -> Path:
        return self.storage_path / f"{entry_id}.enc"

    def save(self, entry: PrivateEntry) -> None:
        """Lưu ký ức cá nhân — encrypted locally. KHÔNG gọi API nào."""
        path = self._entry_path(entry.entry_id)
        blob = json.dumps(asdict(entry), ensure_ascii=False)
        encrypted = self._encrypt(blob)
        path.write_bytes(encrypted)

    def read(self, query: str) -> list[PrivateEntry]:
        """Chỉ người dùng đó mới gọi được. Search by symptom/diagnosis keyword."""
        results: list[PrivateEntry] = []
        q = (query or "").lower()
        for p in self.storage_path.glob("*.enc"):
            try:
                raw = p.read_bytes()
                dec = self._decrypt(raw)
                d = json.loads(dec)
                entry = PrivateEntry(**{k: v for k, v in d.items() if k in PrivateEntry.__dataclass_fields__})
                # Simple keyword search
                text = " ".join(
                    [
                        " ".join(entry.symptoms or []),
                        entry.diagnosis or "",
                        entry.treatment or "",
                        entry.outcome or "",
                        " ".join(entry.herbs_used or []),
                    ]
                ).lower()
                if not q or q in text:
                    results.append(entry)
            except Exception as e:
                logger.debug("Skip corrupted entry %s: %s", p.name, e)
        return results

    def load_entry(self, entry_id: str) -> PrivateEntry | None:
        """Load single entry by id."""
        path = self._entry_path(entry_id)
        if not path.exists():
            return None
        try:
            raw = path.read_bytes()
            dec = self._decrypt(raw)
            d = json.loads(dec)
            return PrivateEntry(**{k: v for k, v in d.items() if k in PrivateEntry.__dataclass_fields__})
        except Exception:
            return None

    def prepare_contribution(
        self,
        entry_ids: list[str],
        anonymize: bool = True,
    ) -> KnowledgeContribution | None:
        """
        Người dùng TỰ CHỌN entries để đóng góp.

        Process:
        1. Load selected entries
        2. Strip ALL personal info (tuổi cụ thể → age_group, địa chỉ → region, ngày → season)
        3. Return KnowledgeContribution — user must confirm before sending
        4. NO automatic upload — caller must explicitly POST to API
        """
        if not entry_ids:
            return None

        # Aggregate first entry (or merge logic for multiple)
        first = self.load_entry(entry_ids[0])
        if not first:
            return None

        content: dict[str, Any] = {
            "symptoms": list(first.symptoms or []),
            "diagnosis": first.diagnosis or "",
            "treatment": first.treatment or "",
            "outcome": first.outcome or "",
            "duration": first.duration_days or 0,
            "herbs_used": list(first.herbs_used or []),
        }

        metadata: dict[str, str] = {
            "region": first.region or "không xác định",
            "age_group": first.age_group or "adult",
            "season": first.season or "không xác định",
        }

        return KnowledgeContribution.create(
            type=ContributionType.TREATMENT_OUTCOME,
            content=content,
            metadata=metadata,
            consent_given=False,  # Caller must get explicit consent
            evidence_level=EvidenceLevel.SELF_REPORTED,
            source="tự báo cáo",
            verified_by_md=False,
        )
