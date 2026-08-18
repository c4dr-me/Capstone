"""Supported Member 1 public API. Consumers must not import repository internals."""

from datetime import datetime, timezone
import re
from typing import Callable

from contracts.access import AccessContext, AuthenticatedSession
from contracts.authorization import (
    ApprovalDecision,
    ApprovalRecord,
    AuthorizationRequest,
    AuthorizationResponse,
)
from contracts.enums import ApprovalOutcome, CanonicalRole
from contracts.errors import GovernanceError
from contracts.execution import ExecutionResult
from contracts.lineage import CaseLineage
from contracts.receipts import GovernanceReceipt

from .access_context import AccessContextService
from .authorization import evaluate_authorization
from .cases import CaseRepository, ParquetCaseRepository
from .integrity import hmac_sha256, payload_sha256
from .models import StoredAuthorization
from .permissions import Permission, has_permission
from .ports import GovernanceRepository
from .receipts import ReceiptFactory
from .settings import GovernanceSettings


def _stable_id(prefix: str, source: str) -> str:
    suffix = re.sub(r"^(REQ|AUTH|RCP)-", "", source, count=1)
    safe = re.sub(r"[^A-Za-z0-9_.:-]", "-", suffix).strip("-")
    if not safe:
        safe = payload_sha256({"source": source})[-16:]
    return f"{prefix}-{safe}"


class GovernanceService:
    def __init__(
        self,
        *,
        repository: GovernanceRepository,
        case_repository: CaseRepository,
        access_contexts: AccessContextService,
        receipts: ReceiptFactory,
        receipt_signing_key: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._cases = case_repository
        self._contexts = access_contexts
        self._receipts = receipts
        self._receipt_signing_key = receipt_signing_key
        self._now = now or (lambda: datetime.now(timezone.utc))

    def mint_access_context(self, session: AuthenticatedSession) -> AccessContext:
        return self._contexts.mint(session)

    def validate_access_context(self, context: AccessContext) -> AccessContext:
        return self._contexts.validate(context)

    def authorize_action(
        self,
        request: AuthorizationRequest,
        access_context: AccessContext,
    ) -> AuthorizationResponse:
        context = self._contexts.validate(access_context)
        if request.access_context_id != context.context_id:
            raise GovernanceError("ACCESS_CONTEXT_MISMATCH", "The request does not reference this access context.")

        request_hash = payload_sha256(request)
        replay = self._repository.find_authorization(request.request_id, context.tenant_id)
        if replay is not None:
            if replay.request_hash != request_hash:
                raise GovernanceError("CONFLICTING_REPLAY", "The request ID was already used with different content.")
            return replay.response

        case = self._cases.get_case(request.exception_id)
        result = evaluate_authorization(request, context, case)
        authorization_id = _stable_id("AUTH", request.request_id)
        receipt_id = _stable_id("RCP", request.request_id)
        response = AuthorizationResponse(
            authorization_id=authorization_id,
            receipt_id=receipt_id,
            decision=result.decision,
            reason_codes=result.reason_codes,
            requires_human=result.requires_human,
            required_approver_role=result.required_approver_role,
            policy_citations=result.policy_citations,
        )
        receipt = self._receipts.initial(request, response, context, case)
        record = StoredAuthorization(
            request=request,
            request_hash=request_hash,
            response=response,
            requester_context=context,
            case=case,
            receipt=receipt,
            decided_at=self._now().astimezone(timezone.utc),
        )
        persisted = self._repository.persist_authorization(record)
        return persisted.response

    def record_approval(
        self,
        decision: ApprovalDecision,
        access_context: AccessContext,
    ) -> ApprovalDecision:
        context = self._contexts.validate(access_context)
        if decision.access_context_id != context.context_id:
            raise GovernanceError("ACCESS_CONTEXT_MISMATCH", "The approval does not reference this access context.")
        stored = self._repository.get_authorization(decision.authorization_id)
        if stored is None:
            raise GovernanceError("AUTHORIZATION_NOT_FOUND", "The pending authorization does not exist.")
        if stored.requester_context.tenant_id != context.tenant_id:
            raise GovernanceError("CROSS_TENANT_CONTEXT", "The approval tenant does not match the authorization.")

        if stored.approval is not None:
            previous = stored.approval
            identical = all(
                getattr(previous, field) == getattr(decision, field)
                for field in (
                    "approval_id",
                    "authorization_id",
                    "access_context_id",
                    "decision",
                    "comment",
                )
            )
            if identical:
                return decision
            self._repository.audit_approval_conflict(
                decision.authorization_id,
                decision.approval_id,
                str(decision.decision),
                context.user_id,
            )
            raise GovernanceError("CONFLICTING_APPROVAL", "A different approval decision was already recorded.")

        try:
            self._validate_approver(stored, context)
        except GovernanceError:
            self._repository.audit_approval_conflict(
                decision.authorization_id,
                decision.approval_id,
                str(decision.decision),
                context.user_id,
            )
            raise

        decided_at = self._now().astimezone(timezone.utc)
        unsigned = decision.model_dump() | {
            "approver_id": context.user_id,
            "approver_role": context.canonical_role,
            "decided_at": decided_at,
        }
        approval = ApprovalRecord(
            **unsigned,
            integrity_hash=hmac_sha256(unsigned, self._receipt_signing_key),
        )
        updated_receipt = self._receipts.after_approval(stored.receipt, approval)
        try:
            self._repository.persist_approval(stored.response.authorization_id, approval, updated_receipt)
        except GovernanceError as exc:
            if exc.error_code == "CONFLICTING_APPROVAL":
                self._repository.audit_approval_conflict(
                    decision.authorization_id,
                    decision.approval_id,
                    str(decision.decision),
                    context.user_id,
                )
            raise
        return decision

    @staticmethod
    def _validate_approver(stored: StoredAuthorization, context: AccessContext) -> None:
        if stored.response.decision != "REQUIRE_APPROVAL":
            raise GovernanceError("APPROVAL_NOT_PENDING", "This authorization does not require approval.")
        if stored.requester_context.user_id == context.user_id:
            raise GovernanceError("MAKER_CHECKER_VIOLATION", "The requester cannot approve their own action.")
        if context.canonical_role in {CanonicalRole.RESOLVEONE_AGENT, CanonicalRole.AUDITOR}:
            raise GovernanceError("INVALID_APPROVER_ROLE", "This principal cannot approve actions.")
        if stored.case.queue not in context.allowed_queues:
            raise GovernanceError("CASE_SCOPE_DENIED", "The approver is not assigned to this case queue.")
        required = stored.response.required_approver_role
        if required == CanonicalRole.OPERATIONS_MANAGER:
            if context.canonical_role != CanonicalRole.OPERATIONS_MANAGER:
                raise GovernanceError("INVALID_APPROVER_ROLE", "An Operations Manager must approve this request.")
            permission = Permission.APPROVE_HIGH_RISK
        else:
            if context.canonical_role not in {
                CanonicalRole.OPERATIONS_ANALYST,
                CanonicalRole.OPERATIONS_MANAGER,
            }:
                raise GovernanceError("INVALID_APPROVER_ROLE", "An eligible operations approver is required.")
            permission = Permission.APPROVE_LOW_RISK
        if not has_permission(context.canonical_role, permission):
            raise GovernanceError("INVALID_APPROVER_ROLE", "The principal lacks approval permission.")

    def create_governance_receipt(
        self,
        authorization_id: str,
        access_context: AccessContext,
    ) -> GovernanceReceipt:
        context = self._contexts.validate(access_context)
        stored = self._repository.get_authorization(authorization_id)
        if stored is None:
            raise GovernanceError("AUTHORIZATION_NOT_FOUND", "The authorization does not exist.")
        receipt = self._repository.get_receipt(stored.response.receipt_id)
        if receipt is None:
            receipt = self._repository.recover_receipt(authorization_id)
        self._enforce_receipt_scope(receipt, context)
        return receipt

    def finalize_governance_receipt(
        self,
        receipt_id: str,
        execution_result: ExecutionResult | None,
        terminal_reason: str | None,
        service_context: AccessContext,
    ) -> GovernanceReceipt:
        context = self._contexts.validate(service_context)
        if context.canonical_role not in {
            CanonicalRole.RESOLVEONE_AGENT,
            CanonicalRole.OPERATIONS_MANAGER,
        }:
            raise GovernanceError("INSUFFICIENT_PERMISSION", "This principal cannot finalize execution receipts.")
        receipt = self._repository.get_receipt(receipt_id)
        if receipt is None:
            raise GovernanceError("RECEIPT_NOT_FOUND", "The governance receipt does not exist.")
        if receipt.tenant_id != context.tenant_id:
            raise GovernanceError("CROSS_TENANT_CONTEXT", "The receipt tenant is not permitted.")
        if str(receipt.action) == "RETRY_PAYMENT" and execution_result is not None:
            raise GovernanceError(
                "LIVE_EXECUTOR_UNAVAILABLE",
                "No live payment executor is connected in the hackathon environment.",
            )
        updated = self._receipts.finalize(receipt, execution_result, terminal_reason)
        if updated == receipt:
            return receipt
        return self._repository.persist_finalization(updated, execution_result)

    def get_governance_receipt(
        self,
        receipt_id: str,
        access_context: AccessContext,
    ) -> GovernanceReceipt:
        context = self._contexts.validate(access_context)
        receipt = self._repository.get_receipt(receipt_id)
        if receipt is None:
            raise GovernanceError("RECEIPT_NOT_FOUND", "The governance receipt does not exist.")
        self._enforce_receipt_scope(receipt, context)
        return receipt

    def _enforce_receipt_scope(self, receipt: GovernanceReceipt, context: AccessContext) -> None:
        if receipt.tenant_id != context.tenant_id:
            raise GovernanceError("CROSS_TENANT_CONTEXT", "The receipt tenant is not permitted.")
        if not has_permission(context.canonical_role, Permission.VIEW_CASE):
            raise GovernanceError("INSUFFICIENT_PERMISSION", "The principal cannot read case receipts.")
        case = self._cases.get_case(receipt.exception_id)
        if case.queue not in context.allowed_queues:
            raise GovernanceError("CASE_SCOPE_DENIED", "The case is outside the principal's queue scope.")

    def get_case_lineage(
        self,
        exception_id: str,
        access_context: AccessContext,
    ) -> CaseLineage:
        context = self._contexts.validate(access_context)
        if not has_permission(context.canonical_role, Permission.VIEW_CASE):
            raise GovernanceError("INSUFFICIENT_PERMISSION", "The principal cannot read case lineage.")
        case = self._cases.get_case(exception_id)
        if case.queue not in context.allowed_queues:
            raise GovernanceError("CASE_SCOPE_DENIED", "The case is outside the principal's queue scope.")
        lineage = self._repository.get_case_lineage(
            exception_id,
            mask_risk_fields=not context.can_view_risk_fields,
        )
        if lineage is None:
            raise GovernanceError("LINEAGE_NOT_FOUND", "No decision lineage exists for the case.")
        return lineage


_SERVICE: GovernanceService | None = None


def _default_service() -> GovernanceService:
    global _SERVICE
    if _SERVICE is None:
        from trust_graph.neo4j_client import Neo4jClient
        from trust_graph.repository import Neo4jGovernanceRepository
        from trust_graph.schema import ensure_schema

        settings = GovernanceSettings.from_env()
        client = Neo4jClient(
            settings.neo4j_uri,
            settings.neo4j_user,
            settings.neo4j_password,
            settings.neo4j_database,
        )
        client.verify_connectivity()
        ensure_schema(client)
        repository = Neo4jGovernanceRepository(client)
        _SERVICE = GovernanceService(
            repository=repository,
            case_repository=ParquetCaseRepository(settings.gold_parquet_path, repository),
            access_contexts=AccessContextService(settings.context_signing_key),
            receipts=ReceiptFactory(settings.receipt_signing_key),
            receipt_signing_key=settings.receipt_signing_key,
        )
    return _SERVICE


def mint_access_context(session: AuthenticatedSession) -> AccessContext:
    return _default_service().mint_access_context(session)


def validate_access_context(context: AccessContext) -> AccessContext:
    return _default_service().validate_access_context(context)


def authorize_action(request: AuthorizationRequest, access_context: AccessContext) -> AuthorizationResponse:
    return _default_service().authorize_action(request, access_context)


def record_approval(decision: ApprovalDecision, access_context: AccessContext) -> ApprovalDecision:
    return _default_service().record_approval(decision, access_context)


def create_governance_receipt(authorization_id: str, access_context: AccessContext) -> GovernanceReceipt:
    return _default_service().create_governance_receipt(authorization_id, access_context)


def finalize_governance_receipt(
    receipt_id: str,
    execution_result: ExecutionResult | None,
    terminal_reason: str | None,
    service_context: AccessContext,
) -> GovernanceReceipt:
    return _default_service().finalize_governance_receipt(
        receipt_id, execution_result, terminal_reason, service_context
    )


def get_governance_receipt(receipt_id: str, access_context: AccessContext) -> GovernanceReceipt:
    return _default_service().get_governance_receipt(receipt_id, access_context)


def get_case_lineage(exception_id: str, access_context: AccessContext) -> CaseLineage:
    return _default_service().get_case_lineage(exception_id, access_context)
