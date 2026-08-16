"""Tamper-evident receipt creation and state-machine transitions."""

from datetime import datetime, timezone
from typing import Callable

from contracts.access import AccessContext
from contracts.authorization import ApprovalRecord, AuthorizationRequest, AuthorizationResponse
from contracts.case import GovernedCase
from contracts.enums import ApprovalOutcome, AuthorizationDecision, ReceiptOutcome, ReceiptState
from contracts.errors import GovernanceError
from contracts.execution import ExecutionResult
from contracts.receipts import GovernanceReceipt, ReceiptRevision

from .integrity import hmac_sha256


class ReceiptFactory:
    def __init__(self, signing_key: str, *, now: Callable[[], datetime] | None = None) -> None:
        if not signing_key:
            raise ValueError("receipt signing key is required")
        self._key = signing_key
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _signed_revision(self, **values: object) -> ReceiptRevision:
        unsigned = ReceiptRevision(integrity_hash="", **values)
        signature = hmac_sha256(unsigned.model_dump(exclude={"integrity_hash"}), self._key)
        return unsigned.model_copy(update={"integrity_hash": signature})

    @staticmethod
    def _project(receipt: GovernanceReceipt, revision: ReceiptRevision) -> GovernanceReceipt:
        return receipt.model_copy(
            update={
                "approval_id": revision.approval_id,
                "receipt_state": revision.receipt_state,
                "outcome": revision.outcome,
                "outcome_reason": revision.outcome_reason,
                "integrity_hash": revision.integrity_hash,
                "timestamp": revision.timestamp,
                "revisions": receipt.revisions + (revision,),
            }
        )

    def initial(
        self,
        request: AuthorizationRequest,
        response: AuthorizationResponse,
        context: AccessContext,
        case: GovernedCase,
    ) -> GovernanceReceipt:
        decision = AuthorizationDecision(response.decision)
        if decision == AuthorizationDecision.DENY:
            state, outcome, reason = (
                ReceiptState.FINAL,
                ReceiptOutcome.NOT_EXECUTED,
                response.reason_codes[0],
            )
        elif decision == AuthorizationDecision.REQUIRE_APPROVAL:
            state, outcome, reason = (
                ReceiptState.PENDING,
                ReceiptOutcome.PENDING_APPROVAL,
                "AWAITING_HUMAN_APPROVAL",
            )
        else:
            state, outcome, reason = (
                ReceiptState.PENDING,
                ReceiptOutcome.PENDING_EXECUTION,
                "AUTHORIZED_PENDING_EXECUTION",
            )
        timestamp = self._now().astimezone(timezone.utc)
        revision = self._signed_revision(
            revision_id=f"{response.receipt_id}:REV:1",
            revision_number=1,
            receipt_state=state,
            outcome=outcome,
            outcome_reason=reason,
            authorization=decision,
            timestamp=timestamp,
            previous_integrity_hash=None,
        )
        trace_id = request.trace_id or request.request_id.replace("REQ-", "TRACE-", 1)
        return GovernanceReceipt(
            receipt_id=response.receipt_id,
            authorization_id=response.authorization_id,
            request_id=request.request_id,
            trace_id=trace_id,
            tenant_id=context.tenant_id,
            exception_id=case.exception_id,
            user_id=context.user_id,
            canonical_role=context.canonical_role,
            agent_id=request.agent_id,
            policy_citations=response.policy_citations,
            evidence_ids=(f"EVD-{case.exception_id}",),
            reason_codes=response.reason_codes,
            action=request.action,
            authorization=decision,
            approval_id=None,
            receipt_state=state,
            outcome=outcome,
            outcome_reason=reason,
            integrity_hash=revision.integrity_hash,
            timestamp=timestamp,
            revisions=(revision,),
        )

    def after_approval(
        self,
        receipt: GovernanceReceipt,
        approval: ApprovalRecord,
    ) -> GovernanceReceipt:
        if receipt.receipt_state == ReceiptState.FINAL:
            raise GovernanceError("FINAL_RECEIPT_IMMUTABLE", "A finalized receipt cannot be changed.")
        if receipt.outcome != ReceiptOutcome.PENDING_APPROVAL:
            raise GovernanceError("APPROVAL_NOT_PENDING", "The authorization is not awaiting approval.")
        approved = approval.decision == ApprovalOutcome.APPROVE
        revision = self._signed_revision(
            revision_id=f"{receipt.receipt_id}:APR:{approval.approval_id}",
            revision_number=len(receipt.revisions) + 1,
            receipt_state=ReceiptState.PENDING if approved else ReceiptState.FINAL,
            outcome=ReceiptOutcome.PENDING_EXECUTION if approved else ReceiptOutcome.NOT_EXECUTED,
            outcome_reason="APPROVAL_GRANTED" if approved else "APPROVAL_REJECTED",
            authorization=receipt.authorization,
            approval_id=approval.approval_id,
            timestamp=self._now().astimezone(timezone.utc),
            previous_integrity_hash=receipt.integrity_hash,
        )
        return self._project(receipt, revision)

    def finalize(
        self,
        receipt: GovernanceReceipt,
        execution_result: ExecutionResult | None,
        terminal_reason: str | None,
    ) -> GovernanceReceipt:
        if execution_result is not None and terminal_reason is not None:
            raise GovernanceError("INVALID_FINALIZATION", "Provide an execution result or terminal reason, not both.")
        if execution_result is None and not terminal_reason:
            raise GovernanceError("INVALID_FINALIZATION", "A terminal result or reason is required.")
        if receipt.receipt_state == ReceiptState.FINAL:
            expected_outcome = (
                ReceiptOutcome(execution_result.status) if execution_result else ReceiptOutcome.NOT_EXECUTED
            )
            expected_reason = terminal_reason or (
                "SANDBOX_EXECUTION_SUCCESS" if expected_outcome == ReceiptOutcome.SUCCESS else "SANDBOX_EXECUTION_FAILED"
            )
            latest = receipt.revisions[-1]
            if (
                receipt.outcome == expected_outcome
                and receipt.outcome_reason == expected_reason
                and latest.execution_id == (execution_result.execution_id if execution_result else None)
            ):
                return receipt
            raise GovernanceError("FINAL_RECEIPT_IMMUTABLE", "A finalized receipt cannot be changed.")
        if receipt.outcome != ReceiptOutcome.PENDING_EXECUTION:
            raise GovernanceError("EXECUTION_NOT_AUTHORIZED", "The receipt is not pending execution.")
        if execution_result is not None:
            if not execution_result.verified:
                raise GovernanceError("UNVERIFIED_EXECUTION", "Only verified execution results can finalize a receipt.")
            if execution_result.exception_id != receipt.exception_id or execution_result.action != receipt.action:
                raise GovernanceError("EXECUTION_CONTEXT_MISMATCH", "Execution result does not match the receipt.")
            outcome = ReceiptOutcome(execution_result.status)
            reason = (
                "SANDBOX_EXECUTION_SUCCESS"
                if outcome == ReceiptOutcome.SUCCESS
                else "SANDBOX_EXECUTION_FAILED"
            )
            execution_id = execution_result.execution_id
        else:
            outcome = ReceiptOutcome.NOT_EXECUTED
            reason = terminal_reason or "NOT_EXECUTED"
            execution_id = None
        revision = self._signed_revision(
            revision_id=f"{receipt.receipt_id}:FINAL",
            revision_number=len(receipt.revisions) + 1,
            receipt_state=ReceiptState.FINAL,
            outcome=outcome,
            outcome_reason=reason,
            authorization=receipt.authorization,
            approval_id=receipt.approval_id,
            execution_id=execution_id,
            timestamp=self._now().astimezone(timezone.utc),
            previous_integrity_hash=receipt.integrity_hash,
        )
        return self._project(receipt, revision)

    def verify_chain(self, receipt: GovernanceReceipt) -> bool:
        previous: str | None = None
        for index, revision in enumerate(receipt.revisions, start=1):
            if revision.revision_number != index or revision.previous_integrity_hash != previous:
                return False
            expected = hmac_sha256(revision.model_dump(exclude={"integrity_hash"}), self._key)
            if expected != revision.integrity_hash:
                return False
            previous = revision.integrity_hash
        return bool(receipt.revisions) and receipt.integrity_hash == previous
