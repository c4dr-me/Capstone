"""LangGraph state graph implementing implementation.md section 9's flow:

Receive exception -> Validate contract -> Fetch governed evidence ->
Calculate severity and queue -> Retrieve the relevant resolution policy ->
Generate an evidence-backed explanation -> Run policy and safety verification
-> Require human approval where needed -> Record the decision and route the
case.

Each node reads/writes `ExceptionAgentState`. The graph fails closed: any
contract or safety-verification failure halts the flow before a
recommendation is returned.
"""

import logging

from langgraph.graph import END, StateGraph

from agent import evidence as evidence_module
from agent.idempotency import CaseIdempotencyStore
from agent.mdm import resolve_exception_type
from agent.policy_gate import verify_recommendation
from agent.retrieval import retrieve_resolution_policy
from agent.routing import calculate_recommended_queue
from agent.severity import calculate_exception_severity
from agent.state import ExceptionAgentState
from agent.tools import TOOL_REGISTRY, ToolGateway

logger = logging.getLogger(__name__)

REQUIRED_CASE_FIELDS = ["exception_id", "transaction_id", "error_types", "masked_card_id", "amount"]

_idempotency_store = CaseIdempotencyStore()


def validate_contract(state: ExceptionAgentState) -> ExceptionAgentState:
    case = evidence_module.get_exception_case(state["exception_id"])
    errors = []
    if case is None:
        errors.append(f"exception_id '{state['exception_id']}' not found in Gold evidence")
    else:
        for field_name in REQUIRED_CASE_FIELDS:
            if case.get(field_name) in (None, ""):
                errors.append(f"required field '{field_name}' is missing or empty")
        for raw_type in str(case.get("error_types", "")).split(","):
            raw_type = raw_type.strip()
            if raw_type and resolve_exception_type(raw_type) is None:
                errors.append(f"error_types contains an unapproved value: '{raw_type}'")

    state["contract_valid"] = not errors
    state["contract_errors"] = errors
    if not errors:
        state["case"] = case
    return state


def fetch_evidence(state: ExceptionAgentState) -> ExceptionAgentState:
    case = state["case"]
    state["evidence_record_ids"] = [f"TXN-{case['transaction_id']}"]
    state["limitations"] = []
    return state


def score_severity_and_queue(state: ExceptionAgentState) -> ExceptionAgentState:
    severity_result = calculate_exception_severity(state["exception_id"])
    queue, _ = calculate_recommended_queue(state["exception_id"], severity_result=severity_result)
    state["severity"] = severity_result.final_severity
    state["reason_codes"] = severity_result.reason_codes
    state["recommended_queue"] = queue
    return state


def retrieve_policy(state: ExceptionAgentState) -> ExceptionAgentState:
    case = state["case"]
    primary_type = state["reason_codes"][0]
    result = retrieve_resolution_policy(primary_type)
    state["policy_result"] = {
        "policy_id": result.policy_id,
        "policy_title": result.policy_title,
        "policy_version": result.policy_version,
        "responsible_team": result.responsible_team,
        "human_approval_required": result.human_approval_required,
        "citations": result.citations,
        "top_similarity_score": result.top_hit.similarity_score if result.top_hit else None,
        "chunks": [
            {"section_title": hit.section_title, "text": hit.chunk_text, "citation": hit.citation}
            for hit in result.hits
        ],
        "limitations": result.limitations,
    }
    if result.limitations:
        state["limitations"] = state.get("limitations", []) + result.limitations
    if case.get("fraud_label") == "Yes":
        state["limitations"] = state.get("limitations", []) + [
            "fraud_label 'Yes' present — ResolveOne is not a fraud-prediction system; "
            "this signal is supporting context only"
        ]
    return state


def _find_chunk_text(state: ExceptionAgentState, anchor: str) -> str | None:
    for chunk in state["policy_result"]["chunks"]:
        if chunk["citation"].endswith(f"#{anchor}"):
            return chunk["text"]
    return None


def generate_recommendation(state: ExceptionAgentState) -> ExceptionAgentState:
    action_text = _find_chunk_text(state, "recommended-action")
    policy = state["policy_result"]
    if action_text:
        first_paragraph = action_text.split("\n\n")[0]
        recommended_action = " ".join(first_paragraph.split())
    else:
        recommended_action = f"Follow {policy['policy_id']} guidance for {state['reason_codes'][0]}"

    confidence = policy["top_similarity_score"] if policy["top_similarity_score"] is not None else 0.0
    confidence = round(min(max(confidence, 0.0), 1.0), 2)

    state["recommended_action"] = recommended_action
    state["confidence"] = confidence
    state["approval_required"] = bool(policy["human_approval_required"]) or state["severity"] in (
        "HIGH",
        "CRITICAL",
    )
    return state


def verify_policy_and_safety(state: ExceptionAgentState) -> ExceptionAgentState:
    prohibited_text = _find_chunk_text(state, "prohibited-action") or ""
    gate_result = verify_recommendation(
        recommended_action=state["recommended_action"],
        prohibited_action_text=prohibited_text,
        evidence=state["case"],
    )
    state["verification_passed"] = gate_result.passed
    state["verification_reason"] = gate_result.reason
    state["blocked_fields"] = gate_result.blocked_fields
    if not gate_result.passed:
        state["halted"] = True
        state["halt_reason"] = f"policy_gate blocked recommendation: {gate_result.reason}"
    return state


def require_human_approval(state: ExceptionAgentState) -> ExceptionAgentState:
    # This node only records that the case requires a human decision before
    # any controlled action executes; it does not grant approval itself.
    return state


def record_and_route(state: ExceptionAgentState) -> ExceptionAgentState:
    gateway = ToolGateway()
    idempotency_key = f"case:{state['exception_id']}"

    # The idempotency store persists across investigate_exception() calls
    # (unlike the per-call ToolGateway), so it is the source of truth for
    # whether this exception has already been submitted for approval.
    replayed = _idempotency_store.seen(idempotency_key)
    if replayed:
        gateway.seen_idempotency_keys.add(idempotency_key)

    outcome = gateway.call_tool(
        "submit_for_human_approval",
        {"exception_id": state["exception_id"], "idempotency_key": idempotency_key},
        impl=lambda exception_id: {"exception_id": exception_id, "status": "submitted"},
        approval="approved",
    )
    _idempotency_store.mark_seen(idempotency_key)

    state["trace"] = gateway.audit_log
    state["result"] = {
        "exception_id": state["exception_id"],
        "severity": state["severity"],
        "recommended_queue": state["recommended_queue"],
        "recommended_action": state["recommended_action"],
        "reason_codes": state["reason_codes"],
        "policy_id": state["policy_result"]["policy_id"],
        "policy_version": state["policy_result"]["policy_version"],
        "citations": state["policy_result"]["citations"],
        "confidence": state["confidence"],
        "approval_required": state["approval_required"],
        "evidence_record_ids": state["evidence_record_ids"],
        "limitations": state.get("limitations", []),
        "replayed": outcome.replayed,
    }
    return state


def _route_after_contract(state: ExceptionAgentState) -> str:
    return "fetch_evidence" if state["contract_valid"] else END


def _route_after_verification(state: ExceptionAgentState) -> str:
    return "require_human_approval" if state["verification_passed"] else END


def build_graph():
    graph = StateGraph(ExceptionAgentState)
    graph.add_node("validate_contract", validate_contract)
    graph.add_node("fetch_evidence", fetch_evidence)
    graph.add_node("score_severity_and_queue", score_severity_and_queue)
    graph.add_node("retrieve_policy", retrieve_policy)
    graph.add_node("generate_recommendation", generate_recommendation)
    graph.add_node("verify_policy_and_safety", verify_policy_and_safety)
    graph.add_node("require_human_approval", require_human_approval)
    graph.add_node("record_and_route", record_and_route)

    graph.set_entry_point("validate_contract")
    graph.add_conditional_edges(
        "validate_contract", _route_after_contract, {"fetch_evidence": "fetch_evidence", END: END}
    )
    graph.add_edge("fetch_evidence", "score_severity_and_queue")
    graph.add_edge("score_severity_and_queue", "retrieve_policy")
    graph.add_edge("retrieve_policy", "generate_recommendation")
    graph.add_edge("generate_recommendation", "verify_policy_and_safety")
    graph.add_conditional_edges(
        "verify_policy_and_safety",
        _route_after_verification,
        {"require_human_approval": "require_human_approval", END: END},
    )
    graph.add_edge("require_human_approval", "record_and_route")
    graph.add_edge("record_and_route", END)

    return graph.compile()


assert set(TOOL_REGISTRY) >= {"submit_for_human_approval"}
