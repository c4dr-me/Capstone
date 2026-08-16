"""Stable values used across governance, agent, and orchestration boundaries."""

from enum import StrEnum


class Action(StrEnum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    SIMULATE_RETRY_PAYMENT = "SIMULATE_RETRY_PAYMENT"
    ESCALATE = "ESCALATE"
    REFUND_PAYMENT = "REFUND_PAYMENT"  # Known but unsupported in the hackathon.


class CanonicalRole(StrEnum):
    OPERATIONS_ANALYST = "OPERATIONS_ANALYST"
    RISK_ANALYST = "RISK_ANALYST"
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"
    AUDITOR = "AUDITOR"
    RESOLVEONE_AGENT = "RESOLVEONE_AGENT"


class FraudLabel(StrEnum):
    YES = "Yes"
    NO = "No"
    UNKNOWN = "Unknown"


class AuthorizationDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ApprovalOutcome(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ReceiptState(StrEnum):
    PENDING = "PENDING"
    FINAL = "FINAL"


class ReceiptOutcome(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PENDING_EXECUTION = "PENDING_EXECUTION"
    NOT_EXECUTED = "NOT_EXECUTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
