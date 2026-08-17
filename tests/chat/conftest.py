"""Fixtures for chat tests."""

import pytest
from datetime import datetime, timedelta, timezone

from contracts.access import AccessContext
from contracts.enums import CanonicalRole


@pytest.fixture
def valid_ops_context() -> AccessContext:
    """Operations Analyst access context (can view OPERATIONS queue, no risk fields)."""
    now = datetime.now(timezone.utc)
    return AccessContext(
        context_id="CTX-TEST-OPS-001",
        user_id="ops_01",
        canonical_role=CanonicalRole.OPERATIONS_ANALYST,
        tenant_id="TENANT-DEMO",
        allowed_queues=("OPERATIONS",),
        can_view_risk_fields=False,
        issued_at=now,
        expires_at=now + timedelta(minutes=30),
        integrity_hash="fake-hash-for-testing",
    )


@pytest.fixture
def valid_risk_context() -> AccessContext:
    """Risk Analyst context (can view FRAUD queue and risk fields)."""
    now = datetime.now(timezone.utc)
    return AccessContext(
        context_id="CTX-TEST-RISK-001",
        user_id="risk_01",
        canonical_role=CanonicalRole.RISK_ANALYST,
        tenant_id="TENANT-DEMO",
        allowed_queues=("FRAUD",),
        can_view_risk_fields=True,
        issued_at=now,
        expires_at=now + timedelta(minutes=30),
        integrity_hash="fake-hash-for-testing",
    )


@pytest.fixture
def expired_context() -> AccessContext:
    """Expired access context (should fail validation)."""
    now = datetime.now(timezone.utc)
    return AccessContext(
        context_id="CTX-TEST-EXPIRED",
        user_id="ops_01",
        canonical_role=CanonicalRole.OPERATIONS_ANALYST,
        tenant_id="TENANT-DEMO",
        allowed_queues=("OPERATIONS",),
        can_view_risk_fields=False,
        issued_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=5),  # expired
        integrity_hash="fake-hash-for-testing",
    )
