"""Deterministic authorization and maker-checker approval contracts."""

from datetime import datetime

from .base import ContractModel
from .enums import (
    Action,
    ApprovalOutcome,
    AuthorizationDecision,
    CanonicalRole,
    FraudLabel,
)


class AssertedCaseContext(ContractModel):
    exception_type: str
    amount: float
    fraud_label: FraudLabel


class AuthorizationRequest(ContractModel):
    request_id: str
    access_context_id: str
    agent_id: str
    exception_id: str
    action: Action
    policy_id: str
    asserted_case_context: AssertedCaseContext
    trace_id: str | None = None


class AuthorizationResponse(ContractModel):
    authorization_id: str
    receipt_id: str
    decision: AuthorizationDecision
    reason_codes: tuple[str, ...]
    requires_human: bool
    required_approver_role: CanonicalRole | None
    policy_citations: tuple[str, ...]


class ApprovalDecision(ContractModel):
    approval_id: str
    authorization_id: str
    access_context_id: str
    decision: ApprovalOutcome
    comment: str


class ApprovalRecord(ApprovalDecision):
    approver_id: str
    approver_role: CanonicalRole
    decided_at: datetime
    integrity_hash: str
