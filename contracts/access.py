"""Identity-session input and integrity-protected access context."""

from datetime import datetime

from pydantic import field_validator

from .base import ContractModel
from .enums import CanonicalRole


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class AuthenticatedSession(ContractModel):
    user_id: str
    tenant_id: str = "TENANT-DEMO"
    authenticated: bool = True
    session_id: str | None = None


class AccessContext(ContractModel):
    context_id: str
    user_id: str
    canonical_role: CanonicalRole
    tenant_id: str
    allowed_queues: tuple[str, ...]
    can_view_risk_fields: bool
    issued_at: datetime
    expires_at: datetime
    integrity_hash: str

    _issued_aware = field_validator("issued_at")(_aware)
    _expires_aware = field_validator("expires_at")(_aware)
