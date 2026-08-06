"""LangGraph state schema for the ResolveOne exception-investigation flow."""

from typing import Any, Optional, TypedDict


class ExceptionAgentState(TypedDict, total=False):
    exception_id: str

    # Populated by validate_contract
    contract_valid: bool
    contract_errors: list[str]

    # Populated by fetch_evidence
    case: dict[str, Any]
    evidence_record_ids: list[str]
    limitations: list[str]

    # Populated by score_severity_and_queue
    severity: str
    reason_codes: list[str]
    recommended_queue: str

    # Populated by retrieve_policy
    policy_result: dict[str, Any]

    # Populated by generate_recommendation
    recommended_action: str
    confidence: float

    # Populated by verify_policy_and_safety
    verification_passed: bool
    verification_reason: str
    blocked_fields: list[str]

    # Populated by require_human_approval
    approval_required: bool

    # Populated by record_and_route
    trace: list[dict[str, Any]]
    result: dict[str, Any]
    halted: bool
    halt_reason: Optional[str]
