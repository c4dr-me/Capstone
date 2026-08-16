from datetime import datetime, timezone

import pytest

from contracts import (
    Action,
    ApprovalDecision,
    AuthenticatedSession,
    AuthorizationRequest,
    ExecutionResult,
)
from contracts.errors import GovernanceError


def auth_request(context, exception_id="EXC-HIGH", amount=425.5, action=Action.SIMULATE_RETRY_PAYMENT, request_id="REQ-APPROVAL"):
    return AuthorizationRequest(
        request_id=request_id,
        access_context_id=context.context_id,
        agent_id="recovery_agent",
        exception_id=exception_id,
        action=action,
        policy_id="POL-TECH-001",
        asserted_case_context={
            "exception_type": "Technical Glitch",
            "amount": amount,
            "fraud_label": "No",
        },
    )


def approval(context, authorization_id, *, decision="APPROVE", approval_id="APR-1"):
    return ApprovalDecision(
        approval_id=approval_id,
        authorization_id=authorization_id,
        access_context_id=context.context_id,
        decision=decision,
        comment="Evidence reviewed",
    )


def execution(execution_id="EXEC-1"):
    return ExecutionResult(
        execution_id=execution_id,
        trace_id="TRACE-APPROVAL",
        exception_id="EXC-HIGH",
        action=Action.SIMULATE_RETRY_PAYMENT,
        status="SUCCESS",
        reference="SIM-1",
        verified=True,
        started_at=datetime(2026, 8, 16, 12, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 16, 12, 2, tzinfo=timezone.utc),
    )


def test_maker_checker_and_invalid_approval_roles(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    pending = service.authorize_action(
        auth_request(operator, "EXC-LOW", 120.0, Action.RETRY_PAYMENT, "REQ-OWN"), operator
    )
    with pytest.raises(GovernanceError) as own_error:
        service.record_approval(approval(operator, pending.authorization_id), operator)
    assert own_error.value.error_code == "MAKER_CHECKER_VIOLATION"

    auditor = service.mint_access_context(AuthenticatedSession(user_id="auditor_01"))
    with pytest.raises(GovernanceError) as role_error:
        service.record_approval(approval(auditor, pending.authorization_id), auditor)
    assert role_error.value.error_code == "INVALID_APPROVER_ROLE"


def test_approval_identity_is_derived_and_identical_replay_is_idempotent(service, repository):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    pending = service.authorize_action(auth_request(operator), operator)
    decision = approval(manager, pending.authorization_id)
    assert service.record_approval(decision, manager) == decision
    assert service.record_approval(decision, manager) == decision
    stored = repository.get_authorization(pending.authorization_id)
    assert stored.approval.approver_id == "manager_01"
    assert stored.approval.approver_role == "OPERATIONS_MANAGER"
    assert stored.receipt.receipt_state == "PENDING"
    assert stored.receipt.outcome == "PENDING_EXECUTION"
    assert len(stored.receipt.revisions) == 2


def test_conflicting_second_approval_is_rejected_and_audited(service, repository):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    pending = service.authorize_action(auth_request(operator), operator)
    service.record_approval(approval(manager, pending.authorization_id), manager)
    conflict = approval(manager, pending.authorization_id, decision="REJECT", approval_id="APR-2")
    with pytest.raises(GovernanceError) as error:
        service.record_approval(conflict, manager)
    assert error.value.error_code == "CONFLICTING_APPROVAL"
    assert repository.approval_conflicts[-1]["attempted_decision"] == "REJECT"


def test_rejected_approval_finalizes_not_executed(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    pending = service.authorize_action(auth_request(operator), operator)
    service.record_approval(approval(manager, pending.authorization_id, decision="REJECT"), manager)
    receipt = service.get_governance_receipt(pending.receipt_id, operator)
    assert receipt.receipt_state == "FINAL"
    assert receipt.outcome == "NOT_EXECUTED"
    assert receipt.outcome_reason == "APPROVAL_REJECTED"


def test_receipt_lifecycle_hash_chain_and_final_immutability(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    service_context = service.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
    pending = service.authorize_action(auth_request(operator), operator)
    initial = service.get_governance_receipt(pending.receipt_id, operator)
    assert (initial.receipt_state, initial.outcome) == ("PENDING", "PENDING_APPROVAL")
    service.record_approval(approval(manager, pending.authorization_id), manager)
    finalized = service.finalize_governance_receipt(
        pending.receipt_id, execution(), None, service_context
    )
    assert (finalized.receipt_state, finalized.outcome) == ("FINAL", "SUCCESS")
    assert len(finalized.revisions) == 3
    assert all(
        current.previous_integrity_hash == previous.integrity_hash
        for previous, current in zip(finalized.revisions, finalized.revisions[1:])
    )
    assert service._receipts.verify_chain(finalized)
    assert service.finalize_governance_receipt(
        pending.receipt_id, execution(), None, service_context
    ) == finalized
    with pytest.raises(GovernanceError) as error:
        service.finalize_governance_receipt(
            pending.receipt_id, execution("EXEC-DIFFERENT"), None, service_context
        )
    assert error.value.error_code == "FINAL_RECEIPT_IMMUTABLE"


def test_kill_switch_terminal_reason_is_recorded_without_member1_reading_switch(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    service_context = service.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
    allowed = service.authorize_action(
        auth_request(operator, "EXC-LOW", 120.0, request_id="REQ-KILL"), operator
    )
    receipt = service.finalize_governance_receipt(
        allowed.receipt_id, None, "AUTONOMY_DISABLED", service_context
    )
    assert receipt.outcome == "NOT_EXECUTED"
    assert receipt.outcome_reason == "AUTONOMY_DISABLED"


def test_live_retry_execution_result_is_refused(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    service_context = service.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
    pending = service.authorize_action(
        auth_request(operator, "EXC-LOW", 120.0, Action.RETRY_PAYMENT, "REQ-LIVE"), operator
    )
    service.record_approval(approval(manager, pending.authorization_id), manager)
    live_result = execution().model_copy(
        update={"exception_id": "EXC-LOW", "action": Action.RETRY_PAYMENT}
    )
    with pytest.raises(GovernanceError) as error:
        service.finalize_governance_receipt(pending.receipt_id, live_result, None, service_context)
    assert error.value.error_code == "LIVE_EXECUTOR_UNAVAILABLE"


def test_lineage_is_complete_bounded_and_masks_risk_fields(service):
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    allowed = service.authorize_action(
        auth_request(operator, "EXC-LOW", 120.0, request_id="REQ-LINEAGE"), operator
    )
    masked = service.get_case_lineage("EXC-LOW", operator)
    unmasked = service.get_case_lineage("EXC-LOW", manager)
    assert masked.receipt_id == allowed.receipt_id
    assert masked.completeness == 1.0
    assert 8 <= len(masked.nodes) <= 12
    masked_exception = next(node for node in masked.nodes if node.type == "Exception")
    unmasked_exception = next(node for node in unmasked.nodes if node.type == "Exception")
    assert masked_exception.properties["fraud_label"] == "RESTRICTED"
    assert unmasked_exception.properties["fraud_label"] == "No"
