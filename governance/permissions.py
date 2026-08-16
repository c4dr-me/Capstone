"""Canonical role and agent permissions."""

from enum import StrEnum

from contracts.enums import Action, CanonicalRole


class Permission(StrEnum):
    VIEW_CASE = "VIEW_CASE"
    VIEW_RISK_DATA = "VIEW_RISK_DATA"
    INVESTIGATE = "INVESTIGATE"
    PROPOSE_ACTION = "PROPOSE_ACTION"
    APPROVE_LOW_RISK = "APPROVE_LOW_RISK"
    APPROVE_HIGH_RISK = "APPROVE_HIGH_RISK"
    RETRY_PAYMENT = "RETRY_PAYMENT"
    SIMULATE_RETRY_PAYMENT = "SIMULATE_RETRY_PAYMENT"
    ESCALATE = "ESCALATE"
    VIEW_AUDIT = "VIEW_AUDIT"
    MANAGE_AUTONOMY = "MANAGE_AUTONOMY"


ROLE_PERMISSIONS: dict[CanonicalRole, frozenset[Permission]] = {
    CanonicalRole.OPERATIONS_ANALYST: frozenset(
        {
            Permission.VIEW_CASE,
            Permission.INVESTIGATE,
            Permission.PROPOSE_ACTION,
            Permission.APPROVE_LOW_RISK,
            Permission.RETRY_PAYMENT,
            Permission.SIMULATE_RETRY_PAYMENT,
            Permission.ESCALATE,
        }
    ),
    CanonicalRole.RISK_ANALYST: frozenset(
        {
            Permission.VIEW_CASE,
            Permission.VIEW_RISK_DATA,
            Permission.INVESTIGATE,
            Permission.PROPOSE_ACTION,
            Permission.APPROVE_LOW_RISK,
            Permission.APPROVE_HIGH_RISK,
            Permission.ESCALATE,
        }
    ),
    CanonicalRole.OPERATIONS_MANAGER: frozenset(Permission),
    CanonicalRole.AUDITOR: frozenset(
        {Permission.VIEW_CASE, Permission.VIEW_RISK_DATA, Permission.VIEW_AUDIT}
    ),
    CanonicalRole.RESOLVEONE_AGENT: frozenset(
        {
            Permission.VIEW_CASE,
            Permission.INVESTIGATE,
            Permission.PROPOSE_ACTION,
            Permission.SIMULATE_RETRY_PAYMENT,
            Permission.ESCALATE,
        }
    ),
}


ACTION_PERMISSION: dict[Action, Permission] = {
    Action.RETRY_PAYMENT: Permission.RETRY_PAYMENT,
    Action.SIMULATE_RETRY_PAYMENT: Permission.SIMULATE_RETRY_PAYMENT,
    Action.ESCALATE: Permission.ESCALATE,
}

# An agent may propose these bounded actions. It never grants authorization or executes them.
AGENT_PROPOSAL_PERMISSIONS = frozenset(
    {Action.RETRY_PAYMENT, Action.SIMULATE_RETRY_PAYMENT, Action.ESCALATE}
)


def has_permission(role: CanonicalRole | str, permission: Permission) -> bool:
    canonical = CanonicalRole(role)
    return permission in ROLE_PERMISSIONS[canonical]
