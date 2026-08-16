"""Fixture-backed fake adapter for Member 2/3 development and unit tests.

This module is never selected by production configuration. The real public module fails
closed when Neo4j is unavailable; there is no silent in-memory fallback.
"""

from dataclasses import replace
from datetime import datetime, timezone

from contracts.access import AuthenticatedSession
from contracts.authorization import ApprovalDecision, ApprovalRecord, AuthorizationRequest
from contracts.case import GovernedCase
from contracts.enums import FraudLabel
from contracts.errors import GovernanceError
from contracts.execution import ExecutionResult
from contracts.lineage import CaseLineage, LineageEdge, LineageNode
from contracts.receipts import GovernanceReceipt

from .access_context import AccessContextService
from .api import GovernanceService
from .cases import CaseRepository
from .models import StoredAuthorization
from .ports import GovernanceRepository
from .receipts import ReceiptFactory


class InMemoryCaseRepository(CaseRepository):
    def __init__(self, cases: list[GovernedCase], history: "InMemoryGovernanceRepository") -> None:
        self._cases = {case.exception_id: case for case in cases}
        self._history = history

    def get_case(self, exception_id: str) -> GovernedCase:
        try:
            case = self._cases[exception_id]
        except KeyError as exc:
            raise GovernanceError("CASE_NOT_FOUND", "The requested exception does not exist.") from exc
        return case.model_copy(update={"retry_count": self._history.get_retry_count(exception_id)})


class InMemoryGovernanceRepository(GovernanceRepository):
    def __init__(self) -> None:
        self.authorizations: dict[str, StoredAuthorization] = {}
        self.requests: dict[tuple[str, str], str] = {}
        self.receipts: dict[str, GovernanceReceipt] = {}
        self.executions: dict[str, ExecutionResult] = {}
        self.approval_conflicts: list[dict[str, str]] = []

    def get_retry_count(self, exception_id: str) -> int:
        return sum(1 for item in self.executions.values() if item.exception_id == exception_id)

    def find_authorization(self, request_id: str, tenant_id: str) -> StoredAuthorization | None:
        authorization_id = self.requests.get((tenant_id, request_id))
        return self.authorizations.get(authorization_id) if authorization_id else None

    def get_authorization(self, authorization_id: str) -> StoredAuthorization | None:
        return self.authorizations.get(authorization_id)

    def persist_authorization(self, record: StoredAuthorization) -> StoredAuthorization:
        existing = self.authorizations.get(record.response.authorization_id)
        if existing is not None and existing.request_hash != record.request_hash:
            raise GovernanceError("CONFLICTING_REPLAY", "The authorization ID has different content.")
        stored = existing or record
        self.authorizations[stored.response.authorization_id] = stored
        self.requests[(stored.requester_context.tenant_id, stored.request.request_id)] = stored.response.authorization_id
        self.receipts[stored.receipt.receipt_id] = stored.receipt
        return stored

    def persist_approval(
        self,
        authorization_id: str,
        approval: ApprovalRecord,
        receipt: GovernanceReceipt,
    ) -> StoredAuthorization:
        stored = self.authorizations[authorization_id]
        if stored.approval and stored.approval.integrity_hash != approval.integrity_hash:
            raise GovernanceError("CONFLICTING_APPROVAL", "A conflicting approval already exists.")
        updated = replace(stored, approval=approval, receipt=receipt)
        self.authorizations[authorization_id] = updated
        self.receipts[receipt.receipt_id] = receipt
        return updated

    def audit_approval_conflict(
        self,
        authorization_id: str,
        approval_id: str,
        attempted_decision: str,
        attempted_by: str,
    ) -> None:
        self.approval_conflicts.append(
            {
                "authorization_id": authorization_id,
                "approval_id": approval_id,
                "attempted_decision": attempted_decision,
                "attempted_by": attempted_by,
            }
        )

    def persist_finalization(
        self,
        receipt: GovernanceReceipt,
        execution_result: ExecutionResult | None,
    ) -> GovernanceReceipt:
        self.receipts[receipt.receipt_id] = receipt
        stored = self.authorizations[receipt.authorization_id]
        self.authorizations[receipt.authorization_id] = replace(stored, receipt=receipt)
        if execution_result is not None:
            self.executions[execution_result.execution_id] = execution_result
        return receipt

    def get_receipt(self, receipt_id: str) -> GovernanceReceipt | None:
        return self.receipts.get(receipt_id)

    def recover_receipt(self, authorization_id: str) -> GovernanceReceipt:
        try:
            receipt = self.authorizations[authorization_id].receipt
        except KeyError as exc:
            raise GovernanceError("AUTHORIZATION_NOT_FOUND", "The authorization does not exist.") from exc
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def get_case_lineage(self, exception_id: str, *, mask_risk_fields: bool) -> CaseLineage | None:
        stored = next(
            (item for item in reversed(tuple(self.authorizations.values())) if item.case.exception_id == exception_id),
            None,
        )
        if stored is None:
            return None
        case = stored.case
        fraud = "RESTRICTED" if mask_risk_fields else str(case.fraud_label)
        ids = {
            "transaction": case.transaction_id,
            "exception": case.exception_id,
            "evidence": stored.receipt.evidence_ids[0],
            "agent": stored.request.agent_id,
            "proposal": stored.response.authorization_id.replace("AUTH-", "PROP-", 1),
            "policy": stored.response.policy_citations[0] if stored.response.policy_citations else "NO-POLICY",
            "authorization": stored.response.authorization_id,
            "user": stored.requester_context.user_id,
            "receipt": stored.receipt.receipt_id,
        }
        nodes = (
            LineageNode(id=ids["transaction"], type="Transaction", label="Transaction", properties={}),
            LineageNode(
                id=ids["exception"],
                type="Exception",
                label="Exception",
                properties={"exception_type": case.exception_type, "fraud_label": fraud},
            ),
            LineageNode(id=ids["evidence"], type="EvidenceSnapshot", label="Evidence", properties={}),
            LineageNode(id=ids["agent"], type="Agent", label="Agent", properties={}),
            LineageNode(id=ids["proposal"], type="ProposedAction", label=str(stored.request.action), properties={}),
            LineageNode(id=ids["policy"], type="PolicyVersion", label="Policy", properties={}),
            LineageNode(id=ids["authorization"], type="AuthorizationDecision", label=str(stored.response.decision), properties={}),
            LineageNode(id=ids["user"], type="User", label="Requester", properties={}),
            LineageNode(id=ids["receipt"], type="GovernanceReceipt", label="Receipt", properties={}),
        )
        edges = tuple(
            LineageEdge(source=ids[source], target=ids[target], type=rel)
            for source, target, rel in (
                ("transaction", "exception", "CAUSED"),
                ("exception", "evidence", "SUPPORTED_BY"),
                ("agent", "proposal", "PROPOSED"),
                ("proposal", "exception", "FOR_EXCEPTION"),
                ("proposal", "policy", "EVALUATED_UNDER"),
                ("authorization", "proposal", "DECIDES"),
                ("authorization", "user", "REQUESTED_BY"),
                ("receipt", "authorization", "PROVES"),
            )
        )
        return CaseLineage(
            exception_id=exception_id,
            trace_id=stored.receipt.trace_id,
            nodes=nodes,
            edges=edges,
            receipt_id=stored.receipt.receipt_id,
            completeness=1.0,
        )


def default_fake_cases() -> list[GovernedCase]:
    base = {
        "transaction_id": "TX-DEMO",
        "exception_type": "Technical Glitch",
        "risk": "LOW",
        "severity": "MEDIUM",
        "masked_card_id": "CARD-demo-masked",
        "retry_count": 0,
        "status": "NEW",
        "queue": "OPERATIONS",
    }
    return [
        GovernedCase(
            **base,
            exception_id="EXC-DEMO-LOW",
            amount=120.0,
            fraud_label=FraudLabel.NO,
            high_value=False,
        ),
        GovernedCase(
            **(base | {"risk": "MEDIUM"}),
            exception_id="EXC-DEMO-UNKNOWN",
            amount=120.0,
            fraud_label=FraudLabel.UNKNOWN,
            high_value=False,
        ),
        GovernedCase(
            **(base | {"risk": "HIGH", "severity": "HIGH"}),
            exception_id="EXC-DEMO-HIGH",
            amount=425.5,
            fraud_label=FraudLabel.NO,
            high_value=True,
        ),
        GovernedCase(
            **(base | {"risk": "HIGH", "queue": "FRAUD"}),
            exception_id="EXC-DEMO-FRAUD",
            amount=80.0,
            fraud_label=FraudLabel.YES,
            high_value=False,
        ),
    ]


class FakeGovernanceAdapter:
    """Drop-in public-interface fake; suitable for UI/orchestrator branches."""

    def __init__(self, cases: list[GovernedCase] | None = None) -> None:
        self.repository = InMemoryGovernanceRepository()
        self.service = GovernanceService(
            repository=self.repository,
            case_repository=InMemoryCaseRepository(cases or default_fake_cases(), self.repository),
            access_contexts=AccessContextService("fake-context-key-for-local-development"),
            receipts=ReceiptFactory("fake-receipt-key-for-local-development"),
            receipt_signing_key="fake-receipt-key-for-local-development",
        )

    def mint_access_context(self, session: AuthenticatedSession):
        return self.service.mint_access_context(session)

    def validate_access_context(self, context):
        return self.service.validate_access_context(context)

    def authorize_action(self, request: AuthorizationRequest, access_context):
        return self.service.authorize_action(request, access_context)

    def record_approval(self, decision: ApprovalDecision, access_context):
        return self.service.record_approval(decision, access_context)

    def create_governance_receipt(self, authorization_id: str, access_context):
        return self.service.create_governance_receipt(authorization_id, access_context)

    def finalize_governance_receipt(
        self,
        receipt_id: str,
        execution_result: ExecutionResult | None,
        terminal_reason: str | None,
        service_context,
    ):
        return self.service.finalize_governance_receipt(
            receipt_id, execution_result, terminal_reason, service_context
        )

    def get_governance_receipt(self, receipt_id: str, access_context):
        return self.service.get_governance_receipt(receipt_id, access_context)

    def get_case_lineage(self, exception_id: str, access_context):
        return self.service.get_case_lineage(exception_id, access_context)
