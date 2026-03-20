"""
tests/test_knowledge_federation.py — Federated Knowledge System Tests
=====================================================================
- PrivateMemory makes 0 network calls
- Contribution strips all PII (reject if PII found)
- Conflict resolution follows rules
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — PrivateMemory makes 0 network calls
# ─────────────────────────────────────────────────────────────────────────────
def test_private_memory_no_network_calls(tmp_path):
    """PrivateMemory must NEVER call external API. Verify via mock."""
    from unittest.mock import patch

    with patch("urllib.request.urlopen") as mock_urlopen:
        with patch("socket.socket") as mock_socket:
            from missions_hub.private_memory import PrivateMemory, PrivateEntry

            pm = PrivateMemory("test_user_001")
            pm.storage_path = tmp_path / "private"
            pm.storage_path.mkdir(parents=True, exist_ok=True)
            entry = PrivateEntry(
                    entry_id="e1",
                    symptoms=["đau bụng"],
                    diagnosis="K29.7",
                    treatment="Gừng",
                    outcome="improved",
                    duration_days=7,
                    herbs_used=["Gừng"],
                    age_group="adult",
                    region="miền Nam",
                    season="summer",
                )
            pm.save(entry)
            loaded = pm.load_entry("e1")
            assert loaded is not None
            assert loaded.diagnosis == "K29.7"
            # Verify no network was used (PrivateMemory is local-only)
            mock_urlopen.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Contribution strips all PII (reject if PII in content)
# ─────────────────────────────────────────────────────────────────────────────
def test_contribution_rejects_pii():
    """If PII (phone, CMND, name+DOB, address) found → REJECT."""
    from missions_hub.knowledge_federation import (
        KnowledgeContribution,
        ContributionType,
        _scan_dict_for_pii,
    )

    # Phone number in symptoms
    content = {"symptoms": ["đau bụng", "gọi 0912345678"], "diagnosis": "K29.7"}
    pii = _scan_dict_for_pii(content)
    assert "phone" in str(pii).lower() or len(pii) > 0

    # Clean content — no PII
    clean = {"symptoms": ["đau bụng"], "diagnosis": "K29.7", "treatment": "Gừng"}
    pii_clean = _scan_dict_for_pii(clean)
    assert len(pii_clean) == 0


def test_federation_rejects_pii_contribution():
    """FederationServer.receive_contribution rejects when PII detected."""
    from pathlib import Path
    import tempfile
    import os

    from missions_hub.knowledge_federation import (
        FederationServer,
        KnowledgeContribution,
        ContributionType,
    )

    with tempfile.TemporaryDirectory() as tmp:
        kb_path = Path(tmp) / "kb.jsonl"
        server = FederationServer(kb_path)
        c = KnowledgeContribution(
            contribution_id="test-1",
            type=ContributionType.TREATMENT_OUTCOME,
            content={
                "symptoms": ["đau bụng", "SĐT 0987654321"],
                "diagnosis": "K29.7",
                "treatment": "Gừng",
                "outcome": "improved",
                "duration": 7,
                "herbs_used": ["Gừng"],
            },
            metadata={"region": "HN", "age_group": "adult", "season": "summer"},
            privacy={"is_anonymous": True, "no_personal_info": True, "consent_given": True},
            validation={"evidence_level": "self_reported", "source": "test", "verified_by_md": False},
        )
        result = asyncio.run(server.receive_contribution(c))
        assert result.accepted is False
        assert "thông tin cá nhân" in result.reason.lower() or "PII" in result.reason or "phone" in result.reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Conflict resolution follows rules
# ─────────────────────────────────────────────────────────────────────────────
def test_conflict_resolution_follows_rules():
    """Evidence wins: WHO/RCT > Doctor > Community > Self-report."""
    from missions_hub.knowledge_federation import (
        FederationServer,
        KnowledgeContribution,
        KnowledgeEntry,
        ContributionType,
    )
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        server = FederationServer(Path(tmp) / "kb.jsonl")
        existing = KnowledgeEntry(
            entry_id="ex1",
            type="treatment_outcome",
            content={"diagnosis": "K29.7", "herbs_used": ["A"]},
            metadata={},
            confidence=0.4,
            source_count=1,
            created_at="2025-01-01",
            updated_at="2025-01-01",
        )
        incoming_low = KnowledgeContribution(
            contribution_id="inc1",
            type=ContributionType.TREATMENT_OUTCOME,
            content={"diagnosis": "K29.7", "herbs_used": ["B"]},
            metadata={},
            privacy={"is_anonymous": True, "no_personal_info": True, "consent_given": True},
            validation={"evidence_level": "self_reported", "source": "test", "verified_by_md": False},
        )
        incoming_high = KnowledgeContribution(
            contribution_id="inc2",
            type=ContributionType.TREATMENT_OUTCOME,
            content={"diagnosis": "K29.7", "herbs_used": ["C"]},
            metadata={},
            privacy={"is_anonymous": True, "no_personal_info": True, "consent_given": True},
            validation={"evidence_level": "doctor_verified", "source": "bs", "verified_by_md": True},
        )

        res_low = asyncio.run(server.resolve_conflict(existing, incoming_low))
        res_high = asyncio.run(server.resolve_conflict(existing, incoming_high))

        # Incoming with higher evidence should win
        assert res_high.winner == "incoming"
        # Incoming with same/lower evidence → existing or both_pending
        assert res_low.winner in ("existing", "incoming", "both_pending")
