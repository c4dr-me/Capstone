"""Fixtures for Member 2 chat tests."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from contracts.access import AccessContext
from contracts.enums import CanonicalRole
from chat.adapters.fake_access_context import validate_access_context_offline
from chat.query_service import QueryService


@pytest.fixture
def valid_ops_context() -> AccessContext:
    now = datetime.now(timezone.utc)
    return AccessContext(
        context_id="CTX-TEST-OPS-001", user_id="ops_01",
        canonical_role=CanonicalRole.OPERATIONS_ANALYST, tenant_id="TENANT-DEMO",
        allowed_queues=("OPERATIONS",), can_view_risk_fields=False,
        issued_at=now, expires_at=now + timedelta(minutes=30), integrity_hash="fake-hash-for-testing",
    )


@pytest.fixture
def valid_risk_context() -> AccessContext:
    now = datetime.now(timezone.utc)
    return AccessContext(
        context_id="CTX-TEST-RISK-001", user_id="risk_01",
        canonical_role=CanonicalRole.RISK_ANALYST, tenant_id="TENANT-DEMO",
        allowed_queues=("FRAUD",), can_view_risk_fields=True,
        issued_at=now, expires_at=now + timedelta(minutes=30), integrity_hash="fake-hash-for-testing",
    )


@pytest.fixture
def expired_context() -> AccessContext:
    now = datetime.now(timezone.utc)
    return AccessContext(
        context_id="CTX-TEST-EXPIRED", user_id="ops_01",
        canonical_role=CanonicalRole.OPERATIONS_ANALYST, tenant_id="TENANT-DEMO",
        allowed_queues=("OPERATIONS",), can_view_risk_fields=False,
        issued_at=now - timedelta(hours=1), expires_at=now - timedelta(minutes=5), integrity_hash="fake-hash",
    )


@pytest.fixture
def offline_validator():
    return validate_access_context_offline


@pytest.fixture
def scoped_query_service() -> QueryService:
    return QueryService(data=pd.DataFrame([
        {"exception_id": "EXC-101", "tenant_id": "TENANT-DEMO", "queue": "OPERATIONS", "exception_type": "TECHNICAL_GLITCH", "status": "NEW", "amount": 120.0, "risk": "LOW", "fraud_label": "No", "severity": "HIGH", "retry_count": 0},
        {"exception_id": "EXC-102", "tenant_id": "TENANT-DEMO", "queue": "OPERATIONS", "exception_type": "TECHNICAL_GLITCH", "status": "NEW", "amount": 800.0, "risk": "HIGH", "fraud_label": "No", "severity": "CRITICAL", "retry_count": 0},
        {"exception_id": "EXC-OTHER-TENANT", "tenant_id": "TENANT-OTHER", "queue": "OPERATIONS", "exception_type": "TECHNICAL_GLITCH", "status": "NEW", "amount": 120.0, "risk": "LOW", "fraud_label": "No", "severity": "HIGH", "retry_count": 0},
        {"exception_id": "EXC-FRAUD", "tenant_id": "TENANT-DEMO", "queue": "FRAUD", "exception_type": "TECHNICAL_GLITCH", "status": "NEW", "amount": 90.0, "risk": "HIGH", "fraud_label": "Yes", "severity": "CRITICAL", "retry_count": 0},
    ]))