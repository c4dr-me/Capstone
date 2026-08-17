"""Deterministic ACT fallback: governed case evidence -> ProposedAction."""

import uuid
from typing import Any

from contracts.enums import Action

from chat.guardrails import run_guardrails
from chat.schemas import ProposedAction


def plan_action(text: str, case: dict[str, Any], agent_id: str = "resolveone-chat") -> ProposedAction:
    """Create a bounded proposal from a case that has already passed scope checks."""
    exception_id = str(case["exception_id"])
    exception_type = str(case.get("exception_type", "")).upper()
    text_lower = text.lower()

    if "retry" in text_lower:
        if exception_type != "TECHNICAL_GLITCH":
            raise ValueError("A retry can only be proposed for an in-scope Technical Glitch case.")
        action = Action.SIMULATE_RETRY_PAYMENT
        reason_codes = ("USER_REQUEST", "TECHNICAL_GLITCH")
        explanation = "A sandbox-only retry is proposed, subject to deterministic authorization."
    elif "escalate" in text_lower:
        action = Action.ESCALATE
        reason_codes = ("USER_REQUEST", "ESCALATION")
        explanation = "Escalation is proposed for authorized operational review."
    else:
        raise ValueError("The requested action is not supported.")

    passed, block_reason = run_guardrails(text, action=action)
    if not passed:
        raise ValueError(f"Guardrail blocked request: {block_reason}")

    return ProposedAction(
        proposal_id=f"PROP-{uuid.uuid4().hex[:8].upper()}",
        exception_id=exception_id,
        agent_id=agent_id,
        action=action,
        reason_codes=reason_codes,
        explanation=explanation,
        policy_id="POL-TECH-001",
        policy_version="1.0",
        citations=("POL-TECH-001@1.0",),
        confidence=0.90,
        source_mode="approved_policy_fallback",
    )