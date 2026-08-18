"""Public interface for Member 2's agent, per implementation_team_split.md.

`investigate_exception(exception_id)` is the only function Member 3's
application needs to call. It runs the LangGraph flow end to end and returns
the exact response schema documented in the team split.
"""

from collections.abc import Callable

from agent.graph import build_graph
from agent.state import ExceptionAgentState

_graph = build_graph()


def investigate_exception(exception_id: str, on_step: Callable[[str], None] | None = None) -> dict:
    """Run the LangGraph flow and optionally report each completed graph node."""
    initial_state: ExceptionAgentState = {"exception_id": exception_id}
    final_state: dict = dict(initial_state)
    for update in _graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_state in update.items():
            final_state.update(node_state)
            if on_step is not None:
                on_step(node_name)

    if not final_state.get("contract_valid", False):
        return {
            "exception_id": exception_id,
            "severity": None,
            "recommended_queue": None,
            "recommended_action": None,
            "reason_codes": [],
            "policy_id": None,
            "policy_version": None,
            "citations": [],
            "confidence": 0.0,
            "approval_required": None,
            "evidence_record_ids": [],
            "limitations": final_state.get("contract_errors", ["contract validation failed"]),
            "blocked": True,
            "block_reason": "contract_validation_failed",
        }

    if final_state.get("halted"):
        return {
            "exception_id": exception_id,
            "severity": final_state.get("severity"),
            "recommended_queue": final_state.get("recommended_queue"),
            "recommended_action": None,
            "reason_codes": final_state.get("reason_codes", []),
            "policy_id": final_state.get("policy_result", {}).get("policy_id"),
            "policy_version": final_state.get("policy_result", {}).get("policy_version"),
            "citations": [],
            "confidence": 0.0,
            "approval_required": final_state.get("approval_required"),
            "evidence_record_ids": final_state.get("evidence_record_ids", []),
            "limitations": final_state.get("limitations", []),
            "blocked": True,
            "block_reason": final_state.get("halt_reason", "safety_verification_failed"),
        }

    result = dict(final_state["result"])
    result["blocked"] = False
    result["block_reason"] = None
    return result
