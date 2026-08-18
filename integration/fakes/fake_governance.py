"""Fake governance adapter to simulate Member 1 for integration."""
from __future__ import annotations

import uuid
from typing import Any, Dict
from pathlib import Path
import time
import json

_receipts: Dict[str, Dict[str, Any]] = {}


def validate_access_context(context: Dict[str, Any]) -> Dict[str, Any]:
    # Very small validation for demos
    if "context_id" not in context:
        context = {**context, "context_id": f"CTX-{uuid.uuid4().hex[:8]}"}
    return context


def authorize_action(request: Dict[str, Any], access_context: Dict[str, Any]) -> Dict[str, Any]:
    # Simple deterministic rules for demo
    action = request.get("action")
    fraud = request.get("asserted_case_context", {}).get("fraud_label")
    amount = request.get("asserted_case_context", {}).get("amount", 0)

    decision = "ALLOW"
    reason_codes = ["LOW_RISK", "FIRST_RETRY"]
    requires_human = False
    if fraud == "Yes":
        decision = "DENY"
        reason_codes = ["FRAUD_POSITIVE"]
    if amount and amount > 10000:
        decision = "REQUIRE_APPROVAL"
        requires_human = True

    auth = {
        "authorization_id": f"AUTH-{uuid.uuid4().hex[:8]}",
        "receipt_id": None,
        "decision": decision,
        "reason_codes": reason_codes,
        "requires_human": requires_human,
        "required_approver_role": "OPERATIONS_MANAGER" if requires_human else None,
        "policy_citations": [request.get("policy_id") + "@1.0"],
    }
    return auth


def create_governance_receipt(authorization: Dict[str, Any], request: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    receipt_id = f"RCP-{uuid.uuid4().hex[:8]}"
    receipt = {
        "receipt_id": receipt_id,
        "authorization_id": authorization.get("authorization_id"),
        "request_id": request.get("request_id"),
        "trace_id": trace_id,
        "tenant_id": "TENANT-DEMO",
        "exception_id": request.get("exception_id"),
        "user_id": "ops_01",
        "canonical_role": "OPERATIONS_ANALYST",
        "agent_id": request.get("agent_id"),
        "policy_citations": authorization.get("policy_citations"),
        "evidence_ids": [],
        "reason_codes": authorization.get("reason_codes"),
        "action": request.get("action"),
        "authorization": authorization.get("decision"),
        "approval_id": None,
        "receipt_state": "PENDING" if authorization.get("decision") == "REQUIRE_APPROVAL" else "PENDING",
        "outcome": "PENDING",
        "outcome_reason": None,
        "integrity_hash": "sha256:fake",
        "timestamp": None,
    }
    _receipts[receipt_id] = receipt
    # attach receipt id to authorization
    authorization["receipt_id"] = receipt_id
    return receipt


def finalize_governance_receipt(receipt_id: str, execution_result: Dict[str, Any] | None, terminal_state: str, terminal_reason: str) -> Dict[str, Any]:
    receipt = _receipts.get(receipt_id)
    if not receipt:
        raise KeyError("receipt not found")
    if execution_result is None:
        receipt["receipt_state"] = "FINAL"
        receipt["outcome"] = "NOT_EXECUTED"
        receipt["outcome_reason"] = terminal_reason
    else:
        receipt["receipt_state"] = "FINAL"
        receipt["outcome"] = execution_result.get("status")
        receipt["outcome_reason"] = terminal_reason
    _receipts[receipt_id] = receipt
    return receipt



def get_case_lineage(exception_id: str, access_context: Dict[str, Any]) -> Dict[str, Any]:
    # Richer fake lineage projection for UI visualization and demos
    tx_id = f"TXN-{uuid.uuid4().hex[:8]}"
    ids = {
        "transaction": tx_id,
        "exception": exception_id,
        "evidence": f"EVD-{uuid.uuid4().hex[:8]}",
        "policy": "POL-TECH-001@1.0",
        "agent": "AGENT-FAKE",
        "proposal": f"PROP-{uuid.uuid4().hex[:8]}",
        "authorization": f"AUTH-{uuid.uuid4().hex[:8]}",
        "execution": f"EXEC-{uuid.uuid4().hex[:8]}",
        "receipt": f"RCP-{uuid.uuid4().hex[:8]}",
    }

    nodes = [
        {"id": ids["transaction"], "type": "Transaction", "label": "Transaction", "properties": {}},
        {"id": ids["exception"], "type": "Exception", "label": "Exception", "properties": {}},
        {"id": ids["evidence"], "type": "EvidenceSnapshot", "label": "Evidence", "properties": {}},
        {"id": ids["policy"], "type": "PolicyVersion", "label": "Policy", "properties": {}},
        {"id": ids["agent"], "type": "Agent", "label": "Agent", "properties": {}},
        {"id": ids["proposal"], "type": "ProposedAction", "label": "Proposal", "properties": {}},
        {"id": ids["authorization"], "type": "AuthorizationDecision", "label": "Authorization", "properties": {}},
        {"id": ids["execution"], "type": "ExecutionAttempt", "label": "Execution", "properties": {}},
        {"id": ids["receipt"], "type": "GovernanceReceipt", "label": "Receipt", "properties": {}},
    ]

    edges = [
        {"source": ids["transaction"], "target": ids["exception"], "type": "CAUSES"},
        {"source": ids["exception"], "target": ids["evidence"], "type": "SUPPORTED_BY"},
        {"source": ids["policy"], "target": ids["proposal"], "type": "GROUNDS"},
        {"source": ids["agent"], "target": ids["proposal"], "type": "PROPOSED"},
        {"source": ids["proposal"], "target": ids["authorization"], "type": "EVALUATED_BY"},
        {"source": ids["authorization"], "target": ids["execution"], "type": "AUTHORIZES"},
        {"source": ids["execution"], "target": ids["receipt"], "type": "PRODUCES"},
    ]

    return {
        "exception_id": exception_id,
        "trace_id": f"TRACE-{uuid.uuid4().hex[:8]}",
        "nodes": nodes,
        "edges": edges,
        "receipt_id": ids["receipt"],
        "completeness": 1.0,
    }
