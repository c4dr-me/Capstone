import os
from uuid import uuid4

import pytest

from contracts.case import GovernedCase
from governance.access_context import AccessContextService
from governance.api import GovernanceService
from governance.fakes import InMemoryCaseRepository
from governance.receipts import ReceiptFactory
from trust_graph.neo4j_client import Neo4jClient
from trust_graph.repository import Neo4jGovernanceRepository
from trust_graph.schema import ensure_schema


@pytest.fixture(scope="session")
def neo4j_client():
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        pytest.skip("NEO4J_PASSWORD is not configured; live Neo4j integration tests were not run")
    client = Neo4jClient(
        os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
        os.environ.get("NEO4J_USER", "neo4j"),
        password,
        os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
    try:
        client.verify_connectivity()
    except Exception as exc:
        client.close()
        pytest.skip(f"Neo4j verify_connectivity() failed: {type(exc).__name__}: {exc}")
    ensure_schema(client)
    yield client
    client.close()


@pytest.fixture
def graph_stack(neo4j_client):
    suffix = uuid4().hex[:12].upper()
    exception_id = f"EXC-IT-{suffix}"
    case = GovernedCase(
        exception_id=exception_id,
        transaction_id=f"TX-IT-{suffix}",
        exception_type="Technical Glitch",
        amount=425.5,
        fraud_label="No",
        risk="HIGH",
        severity="HIGH",
        masked_card_id=f"CARD-IT-{suffix}",
        retry_count=0,
        status="NEW",
        high_value=True,
        queue="OPERATIONS",
    )
    repository = Neo4jGovernanceRepository(neo4j_client)
    service = GovernanceService(
        repository=repository,
        case_repository=InMemoryCaseRepository([case], repository),
        access_contexts=AccessContextService("integration-context-key"),
        receipts=ReceiptFactory("integration-receipt-key"),
        receipt_signing_key="integration-receipt-key",
    )
    yield service, repository, suffix, case
    neo4j_client.execute(
        """
        MATCH (node)
        WHERE node.exception_id = $exception_id
           OR node.transaction_id = $transaction_id
           OR node.evidence_id = $evidence_id
           OR node.proposal_id = $proposal_id
           OR node.authorization_id = $authorization_id
           OR node.receipt_id = $receipt_id
           OR node.revision_id STARTS WITH $receipt_prefix
           OR node.approval_id = $approval_id
           OR node.execution_id = $execution_id
           OR node.outcome_id = $outcome_id
        DETACH DELETE node
        """,
        {
            "exception_id": exception_id,
            "transaction_id": case.transaction_id,
            "evidence_id": f"EVD-{exception_id}",
            "proposal_id": f"PROP-IT-{suffix}",
            "authorization_id": f"AUTH-IT-{suffix}",
            "receipt_id": f"RCP-IT-{suffix}",
            "receipt_prefix": f"RCP-IT-{suffix}:",
            "approval_id": f"APR-IT-{suffix}",
            "execution_id": f"EXEC-IT-{suffix}",
            "outcome_id": f"OUT-EXEC-IT-{suffix}",
        },
    )
