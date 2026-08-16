from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contracts import (
    Action,
    ApprovalDecision,
    AuthenticatedSession,
    AuthorizationRequest,
    ExecutionResult,
)
from contracts.errors import GovernanceError
from trust_graph.schema import UNIQUE_IDENTIFIERS, ensure_schema


pytestmark = pytest.mark.neo4j_integration


def test_connectivity_database_selection_and_idempotent_schema(neo4j_client):
    neo4j_client.verify_connectivity()
    ensure_schema(neo4j_client)
    ensure_schema(neo4j_client)
    records, _, _ = neo4j_client.execute("SHOW CONSTRAINTS YIELD name RETURN collect(name) AS names")
    names = set(records[0]["names"])
    assert {
        f"resolveone_{label.lower()}_{prop}_unique"
        for label, prop in UNIQUE_IDENTIFIERS.items()
    } <= names
    records, _, _ = neo4j_client.execute("CALL db.info() YIELD name RETURN name")
    assert records[0]["name"] == neo4j_client.database


def test_atomic_decision_approval_execution_lineage_and_replay(graph_stack, neo4j_client):
    service, repository, suffix, case = graph_stack
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    manager = service.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    service_context = service.mint_access_context(AuthenticatedSession(user_id="resolveone_agent"))
    request = AuthorizationRequest(
        request_id=f"REQ-IT-{suffix}",
        access_context_id=operator.context_id,
        agent_id="recovery_agent",
        exception_id=case.exception_id,
        action=Action.SIMULATE_RETRY_PAYMENT,
        policy_id="POL-TECH-001",
        asserted_case_context={
            "exception_type": "Technical Glitch",
            "amount": 425.5,
            "fraud_label": "No",
        },
    )
    response = service.authorize_action(request, operator)
    assert response.decision == "REQUIRE_APPROVAL"
    assert service.authorize_action(request, operator) == response
    initial = service.get_governance_receipt(response.receipt_id, operator)
    assert len(initial.revisions) == 1

    approval = ApprovalDecision(
        approval_id=f"APR-IT-{suffix}",
        authorization_id=response.authorization_id,
        access_context_id=manager.context_id,
        decision="APPROVE",
        comment="Integration evidence reviewed",
    )
    service.record_approval(approval, manager)
    result = ExecutionResult(
        execution_id=f"EXEC-IT-{suffix}",
        trace_id=f"TRACE-IT-{suffix}",
        exception_id=case.exception_id,
        action=Action.SIMULATE_RETRY_PAYMENT,
        status="SUCCESS",
        reference=f"SIM-IT-{suffix}",
        verified=True,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    final = service.finalize_governance_receipt(response.receipt_id, result, None, service_context)
    assert final.outcome == "SUCCESS"
    assert service._receipts.verify_chain(final)
    assert repository.get_retry_count(case.exception_id) == 1

    lineage = service.get_case_lineage(case.exception_id, manager)
    assert lineage.completeness == 1.0
    assert 8 <= len(lineage.nodes) <= 12
    assert {"CAUSED", "SUPPORTED_BY", "DECIDES", "PROVES", "EXECUTES", "PRODUCED"} <= {
        edge.type for edge in lineage.edges
    }

    records, _, _ = neo4j_client.execute(
        """
        MATCH (decision:AuthorizationDecision {authorization_id: $authorization_id})
        MATCH (receipt:GovernanceReceipt {receipt_id: $receipt_id})
        MATCH (decision)-[decides:DECIDES]->(:ProposedAction)
        MATCH (receipt)-[proves:PROVES]->(decision)
        RETURN count(DISTINCT decision) AS decisions,
               count(DISTINCT receipt) AS receipts,
               count(DISTINCT decides) AS decides_relationships,
               count(DISTINCT proves) AS proves_relationships
        """,
        {"authorization_id": response.authorization_id, "receipt_id": response.receipt_id},
    )
    assert records[0].data() == {
        "decisions": 1,
        "receipts": 1,
        "decides_relationships": 1,
        "proves_relationships": 1,
    }


def test_transaction_rolls_back_when_a_write_fails(neo4j_client):
    probe_id = f"PROBE-{uuid4().hex}"
    with pytest.raises(Exception):
        neo4j_client.execute(
            "CREATE (:Transaction {transaction_id: $probe_id}) "
            "CREATE (:Transaction {transaction_id: $probe_id})",
            {"probe_id": probe_id},
        )
    records, _, _ = neo4j_client.execute(
        "MATCH (probe:Transaction {transaction_id: $probe_id}) RETURN count(probe) AS count",
        {"probe_id": probe_id},
    )
    assert records[0]["count"] == 0


def test_conflicting_repository_replay_creates_no_partial_case_nodes(graph_stack, neo4j_client):
    service, repository, suffix, case = graph_stack
    operator = service.mint_access_context(AuthenticatedSession(user_id="ops_01"))
    request = AuthorizationRequest(
        request_id=f"REQ-IT-{suffix}",
        access_context_id=operator.context_id,
        agent_id="recovery_agent",
        exception_id=case.exception_id,
        action=Action.SIMULATE_RETRY_PAYMENT,
        policy_id="POL-TECH-001",
        asserted_case_context={"exception_type": "Technical Glitch", "amount": 425.5, "fraud_label": "No"},
    )
    response = service.authorize_action(request, operator)
    stored = repository.get_authorization(response.authorization_id)
    conflicting_case = stored.case.model_copy(
        update={"exception_id": f"EXC-PARTIAL-{suffix}", "transaction_id": f"TX-PARTIAL-{suffix}"}
    )
    conflicting = stored.__class__(
        request=stored.request,
        request_hash="sha256:conflict",
        response=stored.response,
        requester_context=stored.requester_context,
        case=conflicting_case,
        receipt=stored.receipt,
        decided_at=stored.decided_at,
        approval=stored.approval,
    )
    with pytest.raises(GovernanceError) as error:
        repository.persist_authorization(conflicting)
    assert error.value.error_code == "CONFLICTING_REPLAY"
    records, _, _ = neo4j_client.execute(
        "MATCH (exc:Exception {exception_id: $exception_id}) RETURN count(exc) AS count",
        {"exception_id": conflicting_case.exception_id},
    )
    assert records[0]["count"] == 0
