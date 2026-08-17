"""Fake access context validator for Member 2 standalone testing.

In production, Member 1's governance.api.validate_access_context would be used.
For Member 2's independent tests, this fake mimics AccessContext shape and expiry logic.
"""

from datetime import datetime, timezone

from contracts.access import AccessContext


def validate_access_context_offline(context: AccessContext) -> AccessContext:
    """Validate AccessContext structure and expiry without real signature checking.

    Args:
        context: AccessContext to validate

    Returns:
        Same context if valid

    Raises:
        ValueError: if expired or missing required fields
    """
    now = datetime.now(timezone.utc)

    # Check required fields
    for field in ("context_id", "user_id", "canonical_role", "tenant_id"):
        if not getattr(context, field):
            raise ValueError(f"AccessContext missing {field}")

    # Check expiry
    if context.expires_at < now:
        raise ValueError("AccessContext has expired")

    # Check issued_at is before expires_at
    if context.issued_at >= context.expires_at:
        raise ValueError("AccessContext issued_at >= expires_at")

    return context
