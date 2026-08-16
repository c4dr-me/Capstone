"""Neo4j implementation of authoritative governance persistence and lineage."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from contracts.access import AccessContext
from contracts.authorization import ApprovalRecord, AuthorizationRequest, AuthorizationResponse
from contracts.case import GovernedCase
from contracts.errors import GovernanceError
from contracts.execution import ExecutionResult
from contracts.lineage import CaseLineage, LineageEdge, LineageNode
from contracts.receipts import GovernanceReceipt
from governance.integrity import canonical_json
from governance.models import StoredAuthorization

from .neo4j_client import Neo4jClient


AUTHORIZATION_WRITE = """
MERGE (decision:AuthorizationDecision {authorization_id: $authorization_id})
  ON CREATE SET decision.request_id = $request_id,
                decision.tenant_id = $tenant_id,
                decision.request_hash = $request_hash,
                decision.request_json = $request_json,
                decision.response_json = $response_json,
                decision.context_json = $context_json,
                decision.case_json = $case_json,
                decision.receipt_json = $receipt_json,
                decision.decided_at = $decided_at
WITH decision
WHERE decision.request_hash = $request_hash
MERGE (tx:Transaction {transaction_id: $transaction_id})
  ON CREATE SET tx.tenant_id = $tenant_id
MERGE (exc:Exception {exception_id: $exception_id})
  ON CREATE SET exc.tenant_id = $tenant_id,
                exc.exception_type = $exception_type,
                exc.amount = $amount,
                exc.fraud_label = $fraud_label,
                exc.masked_card_id = $masked_card_id,
                exc.queue = $queue
MERGE (tx)-[:CAUSED]->(exc)
MERGE (ev:EvidenceSnapshot {evidence_id: $evidence_id})
  ON CREATE SET ev.tenant_id = $tenant_id, ev.source = 'gold_exception_cases.parquet'
MERGE (exc)-[:SUPPORTED_BY]->(ev)
MERGE (agent:Agent {agent_id: $agent_id})
MERGE (action:ProposedAction {proposal_id: $proposal_id})
  ON CREATE SET action.action = $action, action.request_id = $request_id,
                action.tenant_id = $tenant_id
MERGE (agent)-[:PROPOSED]->(action)
MERGE (action)-[:FOR_EXCEPTION]->(exc)
FOREACH (citation IN $policy_citations |
  MERGE (policy:PolicyVersion {policy_key: citation})
  MERGE (action)-[:EVALUATED_UNDER]->(policy)
)
MERGE (usr:User {user_id: $user_id})
  ON CREATE SET usr.tenant_id = $tenant_id
MERGE (role:Role {role_id: $role_id})
MERGE (usr)-[:HAS_ROLE]->(role)
MERGE (decision)-[:DECIDES]->(action)
MERGE (decision)-[:REQUESTED_BY]->(usr)
MERGE (receipt:GovernanceReceipt {receipt_id: $receipt_id})
  ON CREATE SET receipt.tenant_id = $tenant_id,
                receipt.authorization_id = $authorization_id,
                receipt.exception_id = $exception_id,
                receipt.latest_revision_id = $revision_id,
                receipt.receipt_json = $receipt_json
MERGE (receipt)-[:PROVES]->(decision)
MERGE (revision:ReceiptRevision {revision_id: $revision_id})
  ON CREATE SET revision.receipt_id = $receipt_id,
                revision.revision_number = 1,
                revision.integrity_hash = $revision_hash,
                revision.revision_json = $revision_json,
                revision.finalized = $revision_finalized
MERGE (receipt)-[:HAS_REVISION]->(revision)
RETURN decision.authorization_id AS authorization_id
"""


APPROVAL_WRITE = """
MATCH (decision:AuthorizationDecision {authorization_id: $authorization_id})
MATCH (receipt:GovernanceReceipt {receipt_id: $receipt_id})-[:PROVES]->(decision)
MATCH (previous:ReceiptRevision {revision_id: $previous_revision_id})
WHERE receipt.latest_revision_id = $previous_revision_id AND previous.finalized = false
OPTIONAL MATCH (existing:Approval)-[:FOR_DECISION]->(decision)
WITH decision, receipt, previous, collect(existing) AS existing_approvals
WHERE size(existing_approvals) = 0 OR
      (size(existing_approvals) = 1 AND existing_approvals[0].approval_id = $approval_id
       AND existing_approvals[0].integrity_hash = $approval_hash)
MERGE (approval:Approval {approval_id: $approval_id})
  ON CREATE SET approval.integrity_hash = $approval_hash,
                approval.decision = $approval_decision,
                approval.approver_id = $approver_id,
                approval.approver_role = $approver_role,
                approval.approval_json = $approval_json,
                approval.decided_at = $decided_at
WITH decision, receipt, previous, approval
WHERE approval.integrity_hash = $approval_hash
MERGE (approver:User {user_id: $approver_id})
  ON CREATE SET approver.tenant_id = $tenant_id
MERGE (role:Role {role_id: $approver_role})
MERGE (approver)-[:HAS_ROLE]->(role)
MERGE (approval)-[:FOR_DECISION]->(decision)
MERGE (approval)-[:APPROVED_BY]->(approver)
MERGE (revision:ReceiptRevision {revision_id: $revision_id})
  ON CREATE SET revision.receipt_id = $receipt_id,
                revision.revision_number = $revision_number,
                revision.integrity_hash = $revision_hash,
                revision.revision_json = $revision_json,
                revision.finalized = $revision_finalized
MERGE (receipt)-[:HAS_REVISION]->(revision)
MERGE (revision)-[:PREVIOUS_REVISION]->(previous)
SET receipt.latest_revision_id = $revision_id,
    receipt.receipt_json = $receipt_json,
    decision.approval_json = $approval_json,
    decision.receipt_json = $receipt_json
RETURN approval.approval_id AS approval_id
"""


FINALIZATION_WRITE = """
MATCH (receipt:GovernanceReceipt {receipt_id: $receipt_id})-[:PROVES]->(decision:AuthorizationDecision)
MATCH (previous:ReceiptRevision {revision_id: $previous_revision_id})
WHERE receipt.latest_revision_id = $previous_revision_id AND previous.finalized = false
OPTIONAL MATCH (existing_attempt:ExecutionAttempt {execution_id: $execution_id})
WITH receipt, decision, previous, existing_attempt
WHERE NOT $has_execution OR existing_attempt IS NULL OR existing_attempt.execution_json = $execution_json
MERGE (revision:ReceiptRevision {revision_id: $revision_id})
  ON CREATE SET revision.receipt_id = $receipt_id,
                revision.revision_number = $revision_number,
                revision.integrity_hash = $revision_hash,
                revision.revision_json = $revision_json,
                revision.finalized = true
MERGE (receipt)-[:HAS_REVISION]->(revision)
MERGE (revision)-[:PREVIOUS_REVISION]->(previous)
SET receipt.latest_revision_id = $revision_id,
    receipt.receipt_json = $receipt_json,
    decision.receipt_json = $receipt_json
WITH receipt, decision
OPTIONAL MATCH (decision)-[:DECIDES]->(action:ProposedAction)
FOREACH (_ IN CASE WHEN $has_execution THEN [1] ELSE [] END |
  MERGE (attempt:ExecutionAttempt {execution_id: $execution_id})
    ON CREATE SET attempt.status = $execution_status,
                  attempt.action = $execution_action,
                  attempt.reference = $execution_reference,
                  attempt.verified = $execution_verified,
                  attempt.execution_json = $execution_json
  MERGE (attempt)-[:EXECUTES]->(action)
  MERGE (outcome:Outcome {outcome_id: $outcome_id})
    ON CREATE SET outcome.status = $execution_status
  MERGE (attempt)-[:PRODUCED]->(outcome)
)
RETURN receipt.receipt_id AS receipt_id
"""


LINEAGE_QUERY = """
MATCH (tx:Transaction)-[:CAUSED]->(exc:Exception {exception_id: $exception_id})
MATCH (exc)-[:SUPPORTED_BY]->(ev:EvidenceSnapshot)
MATCH (agent:Agent)-[:PROPOSED]->(action:ProposedAction)-[:FOR_EXCEPTION]->(exc)
MATCH (decision:AuthorizationDecision)-[:DECIDES]->(action)
MATCH (decision)-[:REQUESTED_BY]->(usr:User)
MATCH (action)-[:EVALUATED_UNDER]->(policy:PolicyVersion)
MATCH (receipt:GovernanceReceipt)-[:PROVES]->(decision)
OPTIONAL MATCH (approval:Approval)-[:FOR_DECISION]->(decision)
OPTIONAL MATCH (attempt:ExecutionAttempt)-[:EXECUTES]->(action)
OPTIONAL MATCH (attempt)-[:PRODUCED]->(outcome:Outcome)
RETURN tx, exc, ev, agent, action, decision, usr, policy, receipt,
       approval, attempt, outcome, decision.decided_at AS decided_at
ORDER BY decided_at DESC
LIMIT 1
"""


class Neo4jGovernanceRepository:
    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    def get_retry_count(self, exception_id: str) -> int:
        records, _, _ = self._client.execute(
            """
            MATCH (attempt:ExecutionAttempt)-[:EXECUTES]->
                  (:ProposedAction)-[:FOR_EXCEPTION]->(:Exception {exception_id: $exception_id})
            WHERE attempt.action IN ['RETRY_PAYMENT', 'SIMULATE_RETRY_PAYMENT']
            RETURN count(attempt) AS retry_count
            """,
            {"exception_id": exception_id},
        )
        return int(records[0]["retry_count"]) if records else 0

    def find_authorization(self, request_id: str, tenant_id: str) -> StoredAuthorization | None:
        records, _, _ = self._client.execute(
            """
            MATCH (decision:AuthorizationDecision {request_id: $request_id, tenant_id: $tenant_id})
            RETURN decision
            LIMIT 1
            """,
            {"request_id": request_id, "tenant_id": tenant_id},
        )
        return self._record_from_node(records[0]["decision"]) if records else None

    def get_authorization(self, authorization_id: str) -> StoredAuthorization | None:
        records, _, _ = self._client.execute(
            "MATCH (decision:AuthorizationDecision {authorization_id: $authorization_id}) RETURN decision LIMIT 1",
            {"authorization_id": authorization_id},
        )
        return self._record_from_node(records[0]["decision"]) if records else None

    @staticmethod
    def _record_from_node(node: Any) -> StoredAuthorization:
        approval_json = node.get("approval_json")
        return StoredAuthorization(
            request=AuthorizationRequest.model_validate_json(node["request_json"]),
            request_hash=node["request_hash"],
            response=AuthorizationResponse.model_validate_json(node["response_json"]),
            requester_context=AccessContext.model_validate_json(node["context_json"]),
            case=GovernedCase.model_validate_json(node["case_json"]),
            receipt=GovernanceReceipt.model_validate_json(node["receipt_json"]),
            decided_at=datetime.fromisoformat(str(node["decided_at"]).replace("Z", "+00:00")),
            approval=ApprovalRecord.model_validate_json(approval_json) if approval_json else None,
        )

    def persist_authorization(self, record: StoredAuthorization) -> StoredAuthorization:
        receipt = record.receipt
        revision = receipt.revisions[0]
        params = {
            "transaction_id": record.case.transaction_id,
            "tenant_id": record.requester_context.tenant_id,
            "exception_id": record.case.exception_id,
            "exception_type": record.case.exception_type,
            "amount": record.case.amount,
            "fraud_label": str(record.case.fraud_label),
            "masked_card_id": record.case.masked_card_id,
            "queue": record.case.queue,
            "evidence_id": receipt.evidence_ids[0],
            "agent_id": record.request.agent_id,
            "proposal_id": record.response.authorization_id.replace("AUTH-", "PROP-", 1),
            "action": str(record.request.action),
            "request_id": record.request.request_id,
            "policy_citations": list(record.response.policy_citations),
            "user_id": record.requester_context.user_id,
            "role_id": str(record.requester_context.canonical_role),
            "authorization_id": record.response.authorization_id,
            "request_hash": record.request_hash,
            "request_json": record.request.model_dump_json(),
            "response_json": record.response.model_dump_json(),
            "context_json": record.requester_context.model_dump_json(),
            "case_json": record.case.model_dump_json(),
            "receipt_json": receipt.model_dump_json(),
            "decided_at": record.decided_at.isoformat(),
            "receipt_id": receipt.receipt_id,
            "revision_id": revision.revision_id,
            "revision_hash": revision.integrity_hash,
            "revision_json": revision.model_dump_json(),
            "revision_finalized": str(revision.receipt_state) == "FINAL",
        }
        records, _, _ = self._client.execute(AUTHORIZATION_WRITE, params)
        if not records:
            raise GovernanceError("CONFLICTING_REPLAY", "The authorization ID already has different content.")
        persisted = self.get_authorization(record.response.authorization_id)
        if persisted is None:
            raise GovernanceError("PERSISTENCE_FAILURE", "The authorization write was not visible.")
        return persisted

    def persist_approval(
        self,
        authorization_id: str,
        approval: ApprovalRecord,
        receipt: GovernanceReceipt,
    ) -> StoredAuthorization:
        revision = receipt.revisions[-1]
        params = {
            "authorization_id": authorization_id,
            "receipt_id": receipt.receipt_id,
            "previous_revision_id": receipt.revisions[-2].revision_id,
            "approval_id": approval.approval_id,
            "approval_hash": approval.integrity_hash,
            "approval_decision": str(approval.decision),
            "approval_json": approval.model_dump_json(),
            "approver_id": approval.approver_id,
            "approver_role": str(approval.approver_role),
            "tenant_id": receipt.tenant_id,
            "decided_at": approval.decided_at.isoformat(),
            "revision_id": revision.revision_id,
            "revision_number": revision.revision_number,
            "revision_hash": revision.integrity_hash,
            "revision_json": revision.model_dump_json(),
            "revision_finalized": str(revision.receipt_state) == "FINAL",
            "receipt_json": receipt.model_dump_json(),
        }
        records, _, _ = self._client.execute(APPROVAL_WRITE, params)
        if not records:
            raise GovernanceError("CONFLICTING_APPROVAL", "A conflicting approval already exists.")
        stored = self.get_authorization(authorization_id)
        if stored is None:
            raise GovernanceError("PERSISTENCE_FAILURE", "The approval write was not visible.")
        return stored

    def audit_approval_conflict(
        self,
        authorization_id: str,
        approval_id: str,
        attempted_decision: str,
        attempted_by: str,
    ) -> None:
        raw = f"{authorization_id}|{approval_id}|{attempted_decision}|{attempted_by}"
        conflict_id = f"ACF-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"
        self._client.execute(
            """
            MERGE (conflict:ApprovalConflict {conflict_id: $conflict_id})
              ON CREATE SET conflict.authorization_id = $authorization_id,
                            conflict.approval_id = $approval_id,
                            conflict.attempted_decision = $attempted_decision,
                            conflict.attempted_by = $attempted_by,
                            conflict.recorded_at = datetime()
            WITH conflict
            MATCH (decision:AuthorizationDecision {authorization_id: $authorization_id})
            MERGE (conflict)-[:CONFLICTED_WITH]->(decision)
            """,
            {
                "conflict_id": conflict_id,
                "authorization_id": authorization_id,
                "approval_id": approval_id,
                "attempted_decision": attempted_decision,
                "attempted_by": attempted_by,
            },
        )

    def persist_finalization(
        self,
        receipt: GovernanceReceipt,
        execution_result: ExecutionResult | None,
    ) -> GovernanceReceipt:
        revision = receipt.revisions[-1]
        execution = execution_result
        params = {
            "receipt_id": receipt.receipt_id,
            "previous_revision_id": receipt.revisions[-2].revision_id,
            "revision_id": revision.revision_id,
            "revision_number": revision.revision_number,
            "revision_hash": revision.integrity_hash,
            "revision_json": revision.model_dump_json(),
            "receipt_json": receipt.model_dump_json(),
            "has_execution": execution is not None,
            "execution_id": execution.execution_id if execution else "",
            "execution_status": str(execution.status) if execution else "",
            "execution_action": str(execution.action) if execution else "",
            "execution_reference": execution.reference if execution else "",
            "execution_verified": execution.verified if execution else False,
            "execution_json": execution.model_dump_json() if execution else "",
            "outcome_id": f"OUT-{execution.execution_id}" if execution else "",
        }
        records, _, _ = self._client.execute(FINALIZATION_WRITE, params)
        if not records:
            raise GovernanceError("PERSISTENCE_FAILURE", "The final receipt write failed atomically.")
        return self.get_receipt(receipt.receipt_id) or receipt

    def get_receipt(self, receipt_id: str) -> GovernanceReceipt | None:
        records, _, _ = self._client.execute(
            "MATCH (receipt:GovernanceReceipt {receipt_id: $receipt_id}) RETURN receipt.receipt_json AS payload",
            {"receipt_id": receipt_id},
        )
        return GovernanceReceipt.model_validate_json(records[0]["payload"]) if records else None

    def recover_receipt(self, authorization_id: str) -> GovernanceReceipt:
        stored = self.get_authorization(authorization_id)
        if stored is None:
            raise GovernanceError("AUTHORIZATION_NOT_FOUND", "The authorization does not exist.")
        receipt = stored.receipt
        revision = receipt.revisions[0]
        self._client.execute(
            """
            MATCH (decision:AuthorizationDecision {authorization_id: $authorization_id})
            MERGE (receipt:GovernanceReceipt {receipt_id: $receipt_id})
              ON CREATE SET receipt.tenant_id = $tenant_id,
                            receipt.authorization_id = $authorization_id,
                            receipt.exception_id = $exception_id,
                            receipt.latest_revision_id = $revision_id,
                            receipt.receipt_json = $receipt_json
            MERGE (receipt)-[:PROVES]->(decision)
            MERGE (revision:ReceiptRevision {revision_id: $revision_id})
              ON CREATE SET revision.receipt_id = $receipt_id,
                            revision.revision_number = 1,
                            revision.integrity_hash = $revision_hash,
                            revision.revision_json = $revision_json,
                            revision.finalized = $finalized
            MERGE (receipt)-[:HAS_REVISION]->(revision)
            """,
            {
                "authorization_id": authorization_id,
                "receipt_id": receipt.receipt_id,
                "tenant_id": receipt.tenant_id,
                "exception_id": receipt.exception_id,
                "revision_id": revision.revision_id,
                "receipt_json": receipt.model_dump_json(),
                "revision_hash": revision.integrity_hash,
                "revision_json": revision.model_dump_json(),
                "finalized": str(revision.receipt_state) == "FINAL",
            },
        )
        return receipt

    def get_case_lineage(self, exception_id: str, *, mask_risk_fields: bool) -> CaseLineage | None:
        records, _, _ = self._client.execute(LINEAGE_QUERY, {"exception_id": exception_id})
        if not records:
            return None
        row = records[0]
        node_specs = [
            ("tx", "Transaction", "transaction_id"),
            ("exc", "Exception", "exception_id"),
            ("ev", "EvidenceSnapshot", "evidence_id"),
            ("agent", "Agent", "agent_id"),
            ("action", "ProposedAction", "proposal_id"),
            ("policy", "PolicyVersion", "policy_key"),
            ("decision", "AuthorizationDecision", "authorization_id"),
            ("usr", "User", "user_id"),
            ("receipt", "GovernanceReceipt", "receipt_id"),
            ("approval", "Approval", "approval_id"),
            ("attempt", "ExecutionAttempt", "execution_id"),
            ("outcome", "Outcome", "outcome_id"),
        ]
        nodes: list[LineageNode] = []
        ids: dict[str, str] = {}
        for key, node_type, id_prop in node_specs:
            entity = row.get(key)
            if entity is None:
                continue
            props = dict(entity)
            identifier = str(props[id_prop])
            if mask_risk_fields and node_type == "Exception" and "fraud_label" in props:
                props["fraud_label"] = "RESTRICTED"
            # Stored JSON blobs are persistence details, not UI lineage fields.
            props = {k: v for k, v in props.items() if not k.endswith("_json")}
            ids[key] = identifier
            nodes.append(LineageNode(id=identifier, type=node_type, label=node_type, properties=props))
        edge_specs = [
            ("tx", "exc", "CAUSED"),
            ("exc", "ev", "SUPPORTED_BY"),
            ("agent", "action", "PROPOSED"),
            ("action", "exc", "FOR_EXCEPTION"),
            ("action", "policy", "EVALUATED_UNDER"),
            ("decision", "action", "DECIDES"),
            ("decision", "usr", "REQUESTED_BY"),
            ("receipt", "decision", "PROVES"),
            ("approval", "decision", "FOR_DECISION"),
            ("attempt", "action", "EXECUTES"),
            ("attempt", "outcome", "PRODUCED"),
        ]
        edges = tuple(
            LineageEdge(source=ids[source], target=ids[target], type=rel)
            for source, target, rel in edge_specs
            if source in ids and target in ids
        )
        required = {"tx", "exc", "ev", "agent", "action", "policy", "decision", "usr", "receipt"}
        completeness = len(required & ids.keys()) / len(required)
        receipt = row["receipt"]
        decision = row["decision"]
        request_payload = json.loads(decision["request_json"])
        trace_id = request_payload.get("trace_id") or request_payload["request_id"].replace("REQ-", "TRACE-", 1)
        return CaseLineage(
            exception_id=exception_id,
            trace_id=trace_id,
            nodes=tuple(nodes[:12]),
            edges=edges,
            receipt_id=str(receipt["receipt_id"]),
            completeness=round(completeness, 4),
        )
