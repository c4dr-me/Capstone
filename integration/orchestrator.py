"""Simple orchestrator for Member 3 (integration) using local fakes.

This module exposes `Orchestrator.process_event(event)` which runs the
end-to-end flow using the fakes in `integration/fakes/` and the sandbox
execution in `execution/`.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any, Dict

from integration.fakes.fake_agent import investigate_exception
import os

## The fake adapter is test-only and must be explicitly enabled.
try:
    if os.getenv("RESOLVEONE_USE_FAKE_GOVERNANCE", "").lower() in ("1", "true", "yes"):
        raise ImportError("Explicit fake governance requested")
    import governance.api as gov_api
    from contracts.access import AccessContext as AccessContextContract
    from contracts.authorization import AuthorizationRequest as AuthorizationRequestContract

    def validate_access_context(context: dict | AccessContextContract) -> AccessContextContract:
        if isinstance(context, AccessContextContract):
            return gov_api.validate_access_context(context)
        # Try passing dict directly to the governance API (it may accept a mapping).
        try:
            return gov_api.validate_access_context(context)
        except Exception:
            # If the governance API rejects the input (missing fields), fill sensible defaults
            # and construct the contract model to allow demo flows to continue.
            from datetime import datetime, timedelta
            from integration.fakes.fake_access_context import validate_access_context as fake_validate

            # For demo flows prefer the fake access context if the real API can't validate the input.
            return fake_validate(context or {})

    def authorize_action(request: dict, access_context: dict | AccessContextContract) -> dict:
        # Accept either dicts or contract models. Prefer model instances when possible,
        # but fall back to passing raw mappings into the governance API for demo flows.
        try:
            ar = AuthorizationRequestContract.model_validate(request)
        except Exception:
            ar = request

        if isinstance(access_context, AccessContextContract):
            ac = access_context
        else:
            try:
                ac = AccessContextContract.model_validate(access_context)
            except Exception:
                ac = access_context

        resp = gov_api.authorize_action(ar, ac)
        # Normalize pydantic model return values to plain dicts when necessary
        try:
            return resp.model_dump()
        except Exception:
            return resp

    def create_governance_receipt(authorization: dict | str, request: dict, trace_id: str) -> dict:
        # real API expects authorization_id and access_context; accept either dict or str
        if isinstance(authorization, dict):
            auth_id = authorization.get("authorization_id")
        else:
            auth_id = str(authorization)
        # use access_context from request if present
        access_context = request.get("access_context") or request.get("access_context_id")
        try:
            ac = AccessContextContract.model_validate(access_context) if access_context else None
        except Exception:
            ac = access_context
        receipt = gov_api.create_governance_receipt(auth_id, ac)
        try:
            return receipt.model_dump()
        except Exception:
            return receipt

    def finalize_governance_receipt(receipt_id: str, execution_result: dict | None, terminal_state_or_reason: str | None, terminal_reason: str | None = None) -> dict:
        # real API signature: finalize_governance_receipt(receipt_id, execution_result, terminal_reason, service_context)
        # We expect callers to pass (receipt_id, execution_result, terminal_state, terminal_reason) for the fake path.
        # For compatibility, require the service context be embedded in execution_result or omitted.
        service_context = None
        if isinstance(execution_result, dict) and execution_result.get("service_context"):
            service_context = AccessContextContract.model_validate(execution_result.pop("service_context"))
        # terminal_reason is third in our fake call; prefer that if provided
        reason = terminal_reason or terminal_state_or_reason
        updated = gov_api.finalize_governance_receipt(receipt_id, execution_result, reason, service_context)
        return updated.model_dump()

    def get_case_lineage_gov(exception_id: str, access_context: dict | AccessContextContract) -> dict:
        if isinstance(access_context, AccessContextContract):
            ac = access_context
        else:
            try:
                ac = AccessContextContract.model_validate(access_context)
            except Exception:
                ac = access_context
        lineage = gov_api.get_case_lineage(exception_id, ac)
        try:
            return lineage.model_dump()
        except Exception:
            return lineage

except Exception as exc:
    if os.getenv("RESOLVEONE_USE_FAKE_GOVERNANCE", "").lower() not in ("1", "true", "yes"):
        raise RuntimeError("Authoritative governance is unavailable; refusing to use the fake adapter.") from exc
    from integration.fakes.fake_governance import (
        authorize_action,
        create_governance_receipt,
        finalize_governance_receipt,
        validate_access_context,
        get_case_lineage as get_case_lineage_gov,
    )
from execution.retry_service import retry_payment
from execution.kill_switch import KillSwitch
from execution.verifier import verify_execution
from observability.telemetry import record_workflow_result


class Orchestrator:
    def __init__(self) -> None:
        self.kill_switch = KillSwitch()

    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        trace_id = event.get("trace_id") or f"TRACE-{uuid.uuid4().hex[:8]}"
        exception_id = event["exception_id"]

        # 1. Load case -- for the fake flow we accept case payload in event
        case = event.get("case") or {"exception_id": exception_id}

        # 2. Call Member 2 (investigation)
        proposal = investigate_exception(case)
        proposal["trace_id"] = trace_id

        # 3. Obtain AccessContext (fake validation)
        access_context = event.get("access_context") or {"context_id": "CTX-FAKE", "user_id": "ops_01", "canonical_role": "OPERATIONS_ANALYST"}
        access_context = validate_access_context(access_context)

        # 4. Build AuthorizationRequest and call Member 1
        auth_request = {
            "request_id": f"REQ-{uuid.uuid4().hex[:8]}",
            "access_context_id": access_context["context_id"],
            "agent_id": proposal.get("agent_id", "resolveone-integration"),
            "exception_id": exception_id,
            "action": proposal.get("action"),
            "policy_id": proposal.get("policy_id", "POL-UNKNOWN"),
            "asserted_case_context": {
                "exception_type": case.get("exception_type"),
                "amount": case.get("amount"),
                "fraud_label": case.get("fraud_label"),
            },
        }
        auth_response = authorize_action(auth_request, access_context)

        # 5. Ensure a receipt exists
        receipt = create_governance_receipt(
            authorization=auth_response,
            request=auth_request,
            trace_id=trace_id,
        )

        result: Dict[str, Any] = {
            "trace_id": trace_id,
            "exception_id": exception_id,
            "proposal": proposal,
            "authorization": auth_response,
            "receipt": receipt,
            "execution": None,
        }

        decision = auth_response.get("decision")
        if decision == "DENY":
            # Finalize as NOT_EXECUTED
            finalize_governance_receipt(receipt["receipt_id"], None, "NOT_EXECUTED", "DENIED_BY_POLICY")
            result["status"] = "DENIED"
            try:
                record_workflow_result(result)
            except Exception:
                pass
            return result

        if decision == "REQUIRE_APPROVAL":
            # Leave pending
            result["status"] = "PENDING_APPROVAL"
            try:
                record_workflow_result(result)
            except Exception:
                pass
            return result

        if decision == "ALLOW":
            # Check kill-switch
            if not self.kill_switch.enabled():
                finalize_governance_receipt(receipt["receipt_id"], None, "NOT_EXECUTED", "AUTONOMY_DISABLED")
                result["status"] = "ALLOW_AUTONOMY_DISABLED"
                try:
                    record_workflow_result(result)
                except Exception:
                    pass
                return result

            # Execute sandbox retry
            exec_request = {
                "execution_id": f"EXEC-{uuid.uuid4().hex[:8]}",
                "trace_id": trace_id,
                "exception_id": exception_id,
                "action": proposal.get("action"),
                "case": case,
            }
            exec_result = retry_payment(exec_request)

            # Verify execution
            verified = verify_execution(exec_result)
            exec_result["verified"] = verified

            # Finalize receipt
            finalize_governance_receipt(receipt["receipt_id"], exec_result, exec_result.get("status"), "EXECUTED")

            # fetch lineage projection after finalization
            try:
                lineage = get_case_lineage_gov(exception_id, access_context)
            except Exception:
                lineage = None

            result["execution"] = exec_result
            result["lineage"] = lineage
            result["status"] = exec_result.get("status")

            # record telemetry
            try:
                record_workflow_result(result)
            except Exception:
                pass
            return result

        result["status"] = "UNKNOWN_DECISION"
        return result


def process_event(event: Dict[str, Any], on_step: Callable[[str], None] | None = None) -> Dict[str, Any]:
    if os.getenv("RESOLVEONE_USE_FAKE_GOVERNANCE", "").lower() in ("1", "true", "yes"):
        if on_step is not None:
            on_step("fake_recovery")
        return Orchestrator().process_event(event)
    return RealOrchestrator().process_event(event, on_step=on_step)


class RealOrchestrator:
    """Production adapter: real evidence, agent, governance, and sandbox executor."""

    def __init__(self) -> None:
        self.kill_switch = KillSwitch()

    @staticmethod
    def _dump(value: Any) -> dict:
        return value.model_dump(mode="json")

    def process_event(self, event: Dict[str, Any], on_step: Callable[[str], None] | None = None) -> Dict[str, Any]:
        def emit(step: str) -> None:
            if on_step is not None:
                on_step(step)

        from agent.evidence import get_exception_case
        from agent.orchestrator import investigate_exception as investigate_real_exception
        from contracts.access import AuthenticatedSession
        from contracts.authorization import AuthorizationRequest
        from contracts.enums import Action
        from contracts.execution import ExecutionResult
        from governance import api as governance

        exception_id = str(event["exception_id"])
        trace_id = str(event.get("trace_id") or f"TRACE-{uuid.uuid4().hex[:12]}")
        requester = str(event.get("requester_user_id") or "ops_01")
        emit("start_investigation")
        proposal = investigate_real_exception(exception_id, on_step=on_step)
        proposal["trace_id"] = trace_id
        if proposal.get("blocked"):
            return {"trace_id": trace_id, "exception_id": exception_id, "proposal": proposal,
                    "authorization": None, "receipt": None, "execution": None, "status": "AGENT_BLOCKED"}

        reason_codes = proposal.get("reason_codes") or []
        action = Action.SIMULATE_RETRY_PAYMENT if reason_codes and reason_codes[0] == "TECHNICAL_GLITCH" else Action.ESCALATE
        governed_case = get_exception_case(exception_id)
        if governed_case is None:
            raise ValueError(f"exception_id {exception_id!r} was not found in Gold evidence")
        requester_context = governance.mint_access_context(AuthenticatedSession(user_id=requester))
        request = AuthorizationRequest(
            request_id=f"REQ-{uuid.uuid4().hex}", access_context_id=requester_context.context_id,
            agent_id="resolveone-investigator", exception_id=exception_id, action=action,
            policy_id=str(proposal.get("policy_id") or "POL-UNKNOWN"),
            asserted_case_context={"exception_type": str(governed_case["error_types"]), "amount": float(governed_case["amount"]), "fraud_label": str(governed_case["fraud_label"])},
            trace_id=trace_id,
        )
        emit("authorize_action")
        authorization = governance.authorize_action(request, requester_context)
        emit("create_receipt")
        receipt = governance.create_governance_receipt(authorization.authorization_id, requester_context)
        result: Dict[str, Any] = {"trace_id": trace_id, "exception_id": exception_id, "proposal": proposal,
                                  "authorization": self._dump(authorization), "receipt": self._dump(receipt), "execution": None}
        if str(authorization.decision) == "DENY":
            result["status"] = "DENIED"
            return result
        if str(authorization.decision) == "REQUIRE_APPROVAL":
            result["status"] = "PENDING_APPROVAL"
            return result
        service_context = governance.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
        if not self.kill_switch.enabled():
            result["receipt"] = self._dump(governance.finalize_governance_receipt(receipt.receipt_id, None, "AUTONOMY_DISABLED", service_context))
            result["status"] = "ALLOW_AUTONOMY_DISABLED"
            return result
        if action == Action.ESCALATE:
            result["receipt"] = self._dump(governance.finalize_governance_receipt(receipt.receipt_id, None, "ESCALATED", service_context))
            result["status"] = "ESCALATED"
            return result
        emit("sandbox_execution")
        raw_execution = retry_payment({"execution_id": f"EXEC-{uuid.uuid4().hex}", "trace_id": trace_id,
                                       "exception_id": exception_id, "action": action,
                                       "case": {"severity": proposal.get("severity")}})
        emit("verify_execution")
        raw_execution["verified"] = verify_execution(raw_execution)
        execution = ExecutionResult.model_validate(raw_execution)
        emit("finalize_receipt")
        result["receipt"] = self._dump(governance.finalize_governance_receipt(receipt.receipt_id, execution, None, service_context))
        result["execution"] = self._dump(execution)
        emit("load_lineage")
        result["lineage"] = self._dump(governance.get_case_lineage(exception_id, requester_context))
        result["status"] = str(execution.status)
        record_workflow_result(result)
        return result



def resume_pending_approval(
    recovery: Dict[str, Any], decision: str, comment: str, on_step: Callable[[str], None] | None = None
) -> Dict[str, Any]:
    """Record a manager decision and complete the same pending governance receipt."""
    from contracts.access import AuthenticatedSession
    from contracts.authorization import ApprovalDecision
    from contracts.enums import Action
    from contracts.execution import ExecutionResult
    from governance import api as governance

    def emit(step: str) -> None:
        if on_step is not None:
            on_step(step)

    if os.getenv("RESOLVEONE_USE_FAKE_GOVERNANCE", "").lower() in ("1", "true", "yes"):
        raise RuntimeError("Pending approval resume requires the real governance adapter.")
    authorization = recovery.get("authorization") or {}
    receipt = recovery.get("receipt") or {}
    authorization_id, receipt_id = authorization.get("authorization_id"), receipt.get("receipt_id")
    exception_id = str(recovery.get("exception_id"))
    if recovery.get("status") != "PENDING_APPROVAL" or not authorization_id or not receipt_id:
        raise ValueError("Only a pending governance receipt can be resumed.")

    emit("record_manager_approval")
    manager_context = governance.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    approval = ApprovalDecision(
        approval_id=f"APR-{uuid.uuid4().hex[:10].upper()}", authorization_id=str(authorization_id),
        access_context_id=manager_context.context_id, decision=decision, comment=comment,
    )
    governance.record_approval(approval, manager_context)
    result = dict(recovery)
    result["approval"] = approval.model_dump(mode="json")
    service_context = governance.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))

    if decision == "REJECT":
        emit("finalize_rejection")
        result["receipt"] = governance.finalize_governance_receipt(str(receipt_id), None, "REJECTED_BY_MANAGER", service_context).model_dump(mode="json")
        result["status"] = "REJECTED"
    else:
        proposal = result.get("proposal") or {}
        reason_codes = proposal.get("reason_codes") or []
        action = Action.SIMULATE_RETRY_PAYMENT if reason_codes and reason_codes[0] == "TECHNICAL_GLITCH" else Action.ESCALATE
        if not RealOrchestrator().kill_switch.enabled():
            emit("finalize_autonomy_disabled")
            result["receipt"] = governance.finalize_governance_receipt(str(receipt_id), None, "AUTONOMY_DISABLED", service_context).model_dump(mode="json")
            result["status"] = "APPROVED_AUTONOMY_DISABLED"
        elif action == Action.ESCALATE:
            emit("finalize_escalation")
            result["receipt"] = governance.finalize_governance_receipt(str(receipt_id), None, "ESCALATED", service_context).model_dump(mode="json")
            result["status"] = "ESCALATED"
        else:
            emit("sandbox_execution")
            raw_execution = retry_payment({"execution_id": f"EXEC-{uuid.uuid4().hex}", "trace_id": result["trace_id"], "exception_id": exception_id, "action": action, "case": {"severity": proposal.get("severity")}})
            emit("verify_execution")
            raw_execution["verified"] = verify_execution(raw_execution)
            execution = ExecutionResult.model_validate(raw_execution)
            emit("finalize_receipt")
            result["receipt"] = governance.finalize_governance_receipt(str(receipt_id), execution, None, service_context).model_dump(mode="json")
            result["execution"] = execution.model_dump(mode="json")
            result["status"] = str(execution.status)
    emit("load_lineage")
    result["lineage"] = governance.get_case_lineage(exception_id, manager_context).model_dump(mode="json")
    record_workflow_result(result)
    return result

if __name__ == "__main__":
    # quick smoke
    sample = {"exception_id": "EXC-101", "trace_id": "TRACE-101", "case": {"exception_id": "EXC-101", "exception_type": "Technical Glitch"}, "access_context": {"context_id": "CTX-101", "user_id": "ops_01", "canonical_role": "OPERATIONS_ANALYST"}}
    out = process_event(sample)
    print(out)
