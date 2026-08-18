"""UI adapter for the governed agent with a transparent local fallback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent.evidence import get_exception_case
from agent.mdm import build_golden_policy_profile, golden_chunks_for
from agent.orchestrator import investigate_exception
from agent.routing import calculate_recommended_queue
from agent.severity import calculate_exception_severity


FALLBACK_LIMITATION = (
    "Live pgvector retrieval is unavailable. This result uses the same "
    "deterministic severity rules and approved golden policy, but it is not a "
    "vector-retrieval evaluation result."
)


def build_local_policy_result(exception_id: str, error: Exception | None = None) -> dict[str, Any]:
    case = get_exception_case(exception_id)
    if case is None:
        raise ValueError(f"exception_id '{exception_id}' not found in Gold evidence")

    severity = calculate_exception_severity(exception_id)
    queue, _ = calculate_recommended_queue(exception_id, severity)
    profile = build_golden_policy_profile()[severity.primary_exception_type]
    chunks = golden_chunks_for(severity.primary_exception_type)
    chunks_by_anchor = {chunk.anchor: chunk for chunk in chunks}
    recommended = chunks_by_anchor["recommended-action"]
    cited_anchors = ["recommended-action", "human-approval-requirement", "sla"]

    return {
        "exception_id": exception_id,
        "severity": severity.final_severity,
        "recommended_queue": queue,
        "recommended_action": recommended.text,
        "reason_codes": severity.reason_codes,
        "policy_id": profile.policy_id,
        "policy_version": profile.version,
        "citations": [
            chunks_by_anchor[anchor].citation
            for anchor in cited_anchors
            if anchor in chunks_by_anchor
        ],
        "confidence": None,
        "approval_required": profile.human_approval_required,
        "evidence_record_ids": [f"TXN-{case['transaction_id']}"],
        "limitations": [FALLBACK_LIMITATION],
        "blocked": False,
        "block_reason": None,
        "source_mode": "approved_policy_fallback",
        "agent_error": type(error).__name__ if error else None,
    }


def run_investigation(exception_id: str, on_step: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Run the public agent contract, falling back without hiding the limitation."""

    try:
        result = investigate_exception(exception_id, on_step=on_step)
    except Exception as error:  # The UI must remain usable when VM services are offline.
        if on_step is not None:
            on_step("approved_policy_fallback")
        return build_local_policy_result(exception_id, error)

    adapted = dict(result)
    adapted["source_mode"] = "langgraph_pgvector"
    adapted["agent_error"] = None
    return adapted
