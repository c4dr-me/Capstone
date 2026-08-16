from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts import (
    Action,
    AuthenticatedSession,
    AuthorizationRequest,
    ExecutionResult,
    FraudLabel,
)
from contracts.errors import GovernanceError


def request(context, exception_id="EXC-LOW", action=Action.SIMULATE_RETRY_PAYMENT, **overrides):
    facts = {
        "EXC-LOW": ("Technical Glitch", 120.0, "No"),
        "EXC-HIGH": ("Technical Glitch", 425.5, "No"),
        "EXC-UNKNOWN": ("Technical Glitch", 120.0, "Unknown"),
        "EXC-FRAUD": ("Technical Glitch", 80.0, "Yes"),
        "EXC-BALANCE": ("Insufficient Balance", 120.0, "No"),
    }
    exception_type, amount, fraud = facts[exception_id]
    values = {
        "request_id": overrides.pop("request_id", f"REQ-{exception_id}-{action}"),
        "access_context_id": context.context_id,
        "agent_id": "recovery_agent",
        "exception_id": exception_id,
        "action": action,
        "policy_id": "POL-TECH-001",
        "asserted_case_context": {
            "exception_type": exception_type,
            "amount": amount,
            "fraud_label": fraud,
        },
    }
    values.update(overrides)
    return AuthorizationRequest(**values)


@pytest.mark.parametrize(
    "action",
    [Action.RETRY_PAYMENT, Action.SIMULATE_RETRY_PAYMENT, Action.ESCALATE],
)
def test_auditor_cannot_mutate(action, service):
    context = service.mint_access_context(AuthenticatedSession(user_id="auditor_01"))
    response = service.authorize_action(request(context, action=action), context)
    assert response.decision == "DENY"
    assert response.reason_codes == ("INSUFFICIENT_PERMISSION",)


def test_agent_can_request_sandbox_retry_but_not_live_retry(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
    simulation = service.authorize_action(request(context, request_id="REQ-AGENT-SIM"), context)
    live = service.authorize_action(
        request(context, action=Action.RETRY_PAYMENT, request_id="REQ-AGENT-LIVE"), context
    )
    assert simulation.decision == "ALLOW"
    assert live.decision == "DENY"
    assert live.reason_codes == ("INSUFFICIENT_PERMISSION",)


@pytest.mark.parametrize("action", [Action.RETRY_PAYMENT, Action.SIMULATE_RETRY_PAYMENT])
def test_fraud_positive_retry_is_denied(action, service):
    context = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    response = service.authorize_action(request(context, "EXC-FRAUD", action), context)
    assert response.decision == "DENY"
    assert response.reason_codes == ("FRAUD_CONTEXT_PRESENT",)


def test_unknown_fraud_and_high_value_simulation_require_manager(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    unknown = service.authorize_action(request(context, "EXC-UNKNOWN"), context)
    high = service.authorize_action(request(context, "EXC-HIGH"), context)
    assert unknown.decision == high.decision == "REQUIRE_APPROVAL"
    assert unknown.required_approver_role == high.required_approver_role == "OPERATIONS_MANAGER"
    assert "FRAUD_STATUS_UNKNOWN" in unknown.reason_codes
    assert "HIGH_VALUE" in high.reason_codes


def test_live_retry_always_requires_human_approval(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    response = service.authorize_action(request(context, action=Action.RETRY_PAYMENT), context)
    assert response.decision == "REQUIRE_APPROVAL"
    assert response.required_approver_role == "OPERATIONS_ANALYST"
    assert "LIVE_RETRY_REQUIRES_APPROVAL" in response.reason_codes


def test_non_technical_simulation_and_unsupported_action_are_denied(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    ineligible = service.authorize_action(request(context, "EXC-BALANCE"), context)
    unsupported_request = request(
        context,
        action=Action.REFUND_PAYMENT,
        request_id="REQ-UNSUPPORTED",
        asserted_case_context={"exception_type": "spoof", "amount": 999, "fraud_label": "Yes"},
    )
    unsupported = service.authorize_action(unsupported_request, context)
    assert ineligible.reason_codes == ("INELIGIBLE_EXCEPTION_TYPE",)
    assert unsupported.reason_codes == ("UNSUPPORTED_ACTION",)


def test_spoofed_case_values_fail_closed(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    spoofed = request(
        context,
        request_id="REQ-SPOOF",
        asserted_case_context={"exception_type": "Technical Glitch", "amount": 1, "fraud_label": "No"},
    )
    response = service.authorize_action(spoofed, context)
    assert response.decision == "DENY"
    assert response.reason_codes == ("CASE_CONTEXT_MISMATCH",)


def test_identity_fields_are_forbidden_in_authorization_request(service):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    payload = request(context).model_dump()
    payload["user_id"] = "manager_01"
    payload["canonical_role"] = "OPERATIONS_MANAGER"
    with pytest.raises(ValidationError):
        AuthorizationRequest(**payload)


def test_context_id_mismatch_rejects_without_decision_or_receipt(service, repository):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    other = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    with pytest.raises(GovernanceError) as error:
        service.authorize_action(request(context), other)
    assert error.value.error_code == "ACCESS_CONTEXT_MISMATCH"
    assert repository.authorizations == {}
    assert repository.receipts == {}


def test_every_decision_has_receipt_and_replay_is_idempotent(service, repository):
    context = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    original = request(context, request_id="REQ-IDEMPOTENT")
    first = service.authorize_action(original, context)
    second = service.authorize_action(original, context)
    assert first == second
    assert len(repository.authorizations) == len(repository.receipts) == 1
    assert service.get_governance_receipt(first.receipt_id, context).authorization_id == first.authorization_id

    conflicting = original.model_copy(update={"action": Action.ESCALATE})
    with pytest.raises(GovernanceError) as error:
        service.authorize_action(conflicting, context)
    assert error.value.error_code == "CONFLICTING_REPLAY"


def test_second_retry_is_denied_from_execution_history(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    service_context = service.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
    first = service.authorize_action(request(operator, request_id="REQ-FIRST"), operator)
    execution = ExecutionResult(
        execution_id="EXEC-FIRST",
        trace_id="TRACE-FIRST",
        exception_id="EXC-LOW",
        action=Action.SIMULATE_RETRY_PAYMENT,
        status="SUCCESS",
        reference="SIM-FIRST",
        verified=True,
        started_at=datetime(2026, 8, 16, 12, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 16, 12, 2, tzinfo=timezone.utc),
    )
    service.finalize_governance_receipt(first.receipt_id, execution, None, service_context)
    second = service.authorize_action(request(operator, request_id="REQ-SECOND"), operator)
    assert second.decision == "DENY"
    assert second.reason_codes == ("RETRY_LIMIT_REACHED",)
