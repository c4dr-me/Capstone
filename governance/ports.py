"""Persistence port implemented by Neo4j and test/development fakes."""

from typing import Protocol

from contracts.authorization import ApprovalRecord
from contracts.execution import ExecutionResult
from contracts.lineage import CaseLineage
from contracts.receipts import GovernanceReceipt

from .models import StoredAuthorization


class GovernanceRepository(Protocol):
    def get_retry_count(self, exception_id: str) -> int: ...

    def find_authorization(self, request_id: str, tenant_id: str) -> StoredAuthorization | None: ...

    def get_authorization(self, authorization_id: str) -> StoredAuthorization | None: ...

    def persist_authorization(self, record: StoredAuthorization) -> StoredAuthorization: ...

    def persist_approval(
        self,
        authorization_id: str,
        approval: ApprovalRecord,
        receipt: GovernanceReceipt,
    ) -> StoredAuthorization: ...

    def audit_approval_conflict(
        self,
        authorization_id: str,
        approval_id: str,
        attempted_decision: str,
        attempted_by: str,
    ) -> None: ...

    def persist_finalization(
        self,
        receipt: GovernanceReceipt,
        execution_result: ExecutionResult | None,
    ) -> GovernanceReceipt: ...

    def get_receipt(self, receipt_id: str) -> GovernanceReceipt | None: ...

    def recover_receipt(self, authorization_id: str) -> GovernanceReceipt: ...

    def get_case_lineage(self, exception_id: str, *, mask_risk_fields: bool) -> CaseLineage | None: ...
