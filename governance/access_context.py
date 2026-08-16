"""Mint and validate short-lived, integrity-protected trusted contexts."""

from datetime import datetime, timedelta, timezone
import secrets
from typing import Callable

from contracts.access import AccessContext, AuthenticatedSession
from contracts.errors import GovernanceError

from .integrity import hmac_sha256, secure_hash_matches
from .roles import DEMO_TENANT, IDENTITIES


CONTEXT_LIFETIME = timedelta(minutes=30)


class AccessContextService:
    def __init__(
        self,
        signing_key: str,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not signing_key:
            raise ValueError("context signing key is required")
        self._key = signing_key
        self._now = now or (lambda: datetime.now(timezone.utc))

    def mint(self, session: AuthenticatedSession) -> AccessContext:
        if not session.authenticated:
            raise GovernanceError("UNAUTHENTICATED", "An authenticated session is required.")
        identity = IDENTITIES.get(session.user_id)
        if identity is None or not identity.active:
            raise GovernanceError("UNKNOWN_USER", "The session principal is not active or recognized.")
        if session.tenant_id != DEMO_TENANT or session.tenant_id != identity.tenant_id:
            raise GovernanceError("CROSS_TENANT_CONTEXT", "The session tenant is not permitted.")
        issued_at = self._now().astimezone(timezone.utc)
        unsigned = {
            "context_id": f"CTX-{secrets.token_hex(8).upper()}",
            "user_id": identity.user_id,
            "canonical_role": identity.canonical_role,
            "tenant_id": identity.tenant_id,
            "allowed_queues": identity.allowed_queues,
            "can_view_risk_fields": identity.can_view_risk_fields,
            "issued_at": issued_at,
            "expires_at": issued_at + CONTEXT_LIFETIME,
        }
        return AccessContext(**unsigned, integrity_hash=hmac_sha256(unsigned, self._key))

    def validate(self, context: AccessContext) -> AccessContext:
        identity = IDENTITIES.get(context.user_id)
        if identity is None or not identity.active:
            raise GovernanceError("UNKNOWN_USER", "The access context principal is not recognized.")
        if context.tenant_id != DEMO_TENANT or context.tenant_id != identity.tenant_id:
            raise GovernanceError("CROSS_TENANT_CONTEXT", "The access context tenant is not permitted.")
        if context.canonical_role != identity.canonical_role:
            raise GovernanceError("WRONG_ROLE", "The access context role does not match trusted identity data.")
        if (
            tuple(context.allowed_queues) != identity.allowed_queues
            or context.can_view_risk_fields != identity.can_view_risk_fields
        ):
            raise GovernanceError("TAMPERED_CONTEXT", "The access scope does not match trusted identity data.")
        now = self._now().astimezone(timezone.utc)
        if context.expires_at <= now or context.issued_at > now:
            raise GovernanceError("EXPIRED_CONTEXT", "The access context is expired or not yet valid.")
        unsigned = context.model_dump(exclude={"integrity_hash"})
        expected = hmac_sha256(unsigned, self._key)
        if not secure_hash_matches(expected, context.integrity_hash):
            raise GovernanceError("TAMPERED_CONTEXT", "The access context integrity check failed.")
        return context
