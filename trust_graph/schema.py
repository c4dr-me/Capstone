"""Community-compatible idempotent uniqueness constraints."""

from .neo4j_client import Neo4jClient


UNIQUE_IDENTIFIERS = {
    "Transaction": "transaction_id",
    "Exception": "exception_id",
    "EvidenceSnapshot": "evidence_id",
    "User": "user_id",
    "Role": "role_id",
    "Agent": "agent_id",
    "PolicyVersion": "policy_key",
    "ProposedAction": "proposal_id",
    "AuthorizationDecision": "authorization_id",
    "Approval": "approval_id",
    "ExecutionAttempt": "execution_id",
    "Outcome": "outcome_id",
    "GovernanceReceipt": "receipt_id",
    "ReceiptRevision": "revision_id",
}


def ensure_schema(client: Neo4jClient) -> None:
    # Labels/properties come only from this static allowlist; no caller data enters query text.
    for label, prop in UNIQUE_IDENTIFIERS.items():
        name = f"resolveone_{label.lower()}_{prop}_unique"
        client.execute(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (node:{label}) REQUIRE node.{prop} IS UNIQUE"
        )
