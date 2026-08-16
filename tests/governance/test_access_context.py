from datetime import timedelta

import pytest

from contracts import AuthenticatedSession, CanonicalRole
from contracts.errors import GovernanceError


def test_context_is_trusted_registry_projection_with_30_minute_lifetime(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    assert context.canonical_role == CanonicalRole.OPERATIONS_ANALYST
    assert context.tenant_id == "TENANT-DEMO"
    assert context.allowed_queues == ("OPERATIONS",)
    assert context.expires_at - context.issued_at == timedelta(minutes=30)
    assert context.integrity_hash.startswith("sha256:")
    assert service.validate_access_context(context) == context


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"allowed_queues": ("FRAUD", "OPERATIONS")}, "TAMPERED_CONTEXT"),
        ({"canonical_role": CanonicalRole.OPERATIONS_MANAGER}, "WRONG_ROLE"),
        ({"tenant_id": "TENANT-OTHER"}, "CROSS_TENANT_CONTEXT"),
        ({"user_id": "unknown_01"}, "UNKNOWN_USER"),
    ],
)
def test_tampered_wrong_role_cross_tenant_and_unknown_user_are_rejected(service, updates, code):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    with pytest.raises(GovernanceError) as error:
        service.validate_access_context(context.model_copy(update=updates))
    assert error.value.error_code == code


def test_expired_context_is_rejected_before_authorization(service, clock):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    clock.value += timedelta(minutes=31)
    with pytest.raises(GovernanceError) as error:
        service.validate_access_context(context)
    assert error.value.error_code == "EXPIRED_CONTEXT"


def test_unknown_session_and_cross_tenant_session_are_rejected(service):
    for session, code in (
        (AuthenticatedSession(user_id="nobody"), "UNKNOWN_USER"),
        (AuthenticatedSession(user_id="ops_01", tenant_id="TENANT-OTHER"), "CROSS_TENANT_CONTEXT"),
    ):
        with pytest.raises(GovernanceError) as error:
            service.mint_access_context(session)
        assert error.value.error_code == code
