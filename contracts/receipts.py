"""Tamper-evident governance receipt and immutable revision contracts."""

from datetime import datetime

from .base import ContractModel
from .enums import Action, AuthorizationDecision, CanonicalRole, ReceiptOutcome, ReceiptState


class ReceiptRevision(ContractModel):
    revision_id: str
    revision_number: int
    receipt_state: ReceiptState
    outcome: ReceiptOutcome
    outcome_reason: str
    authorization: AuthorizationDecision
    approval_id: str | None = None
    execution_id: str | None = None
    timestamp: datetime
    previous_integrity_hash: str | None = None
    integrity_hash: str


class GovernanceReceipt(ContractModel):
    receipt_id: str
    authorization_id: str
    request_id: str
    trace_id: str
    tenant_id: str
    exception_id: str
    user_id: str
    canonical_role: CanonicalRole
    agent_id: str
    policy_citations: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    action: Action
    authorization: AuthorizationDecision
    approval_id: str | None = None
    receipt_state: ReceiptState
    outcome: ReceiptOutcome
    outcome_reason: str
    integrity_hash: str
    timestamp: datetime
    revisions: tuple[ReceiptRevision, ...]
