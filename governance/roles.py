"""Trusted demo identity registry; UI-supplied role strings are never used."""

from dataclasses import dataclass

from contracts.enums import CanonicalRole


DEMO_TENANT = "TENANT-DEMO"


@dataclass(frozen=True)
class Identity:
    user_id: str
    canonical_role: CanonicalRole
    allowed_queues: tuple[str, ...]
    can_view_risk_fields: bool
    active: bool = True
    tenant_id: str = DEMO_TENANT


IDENTITIES: dict[str, Identity] = {
    "ops_01": Identity("ops_01", CanonicalRole.OPERATIONS_ANALYST, ("OPERATIONS",), False),
    "risk_01": Identity("risk_01", CanonicalRole.RISK_ANALYST, ("FRAUD", "RISK"), True),
    "manager_01": Identity(
        "manager_01",
        CanonicalRole.OPERATIONS_MANAGER,
        ("FRAUD", "OPERATIONS", "RISK"),
        True,
    ),
    "auditor_01": Identity(
        "auditor_01",
        CanonicalRole.AUDITOR,
        ("FRAUD", "OPERATIONS", "RISK"),
        True,
    ),
    "resolveone_agent": Identity(
        "resolveone_agent",
        CanonicalRole.RESOLVEONE_AGENT,
        ("FRAUD", "OPERATIONS", "RISK"),
        False,
    ),
}


TRUSTED_AGENT_IDS = frozenset({"resolveone_agent", "recovery_agent", "resolveone-investigator"})
