"""ACT intent handler: natural language → ProposedAction."""

import uuid
from datetime import datetime, timezone

from contracts.enums import Action

from chat.guardrails import run_guardrails
from chat.schemas import ProposedAction


def plan_action(
    text: str,
    exception_id: str,
    agent_id: str = "resolveone-chat",
) -> ProposedAction:
    """Generate a ProposedAction from natural language.

    Args:
        text: user's action request (e.g., "retry this payment")
        exception_id: case ID to act on
        agent_id: agent identity

    Returns:
        ProposedAction ready for authorization

    Raises:
        ValueError: if guardrails reject the request
    """
    text_lower = text.lower()

    # Determine action from text
    if "retry" in text_lower:
        action = Action.SIMULATE_RETRY_PAYMENT
        reason_codes = ("USER_REQUEST", "TECHNICAL_GLITCH")
        explanation = "User requested a controlled retry."
    elif "escalate" in text_lower:
        action = Action.ESCALATE
        reason_codes = ("USER_REQUEST", "ESCALATION")
        explanation = "User requested escalation to fraud analysis."
    else:
        action = Action.ESCALATE
        reason_codes = ("USER_REQUEST",)
        explanation = "User requested action on the case."

    # Run guardrails on the intent
    passed, block_reason = run_guardrails(text, action=action)
    if not passed:
        raise ValueError(f"Guardrail blocked request: {block_reason}")

    proposal = ProposedAction(
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
    )

    return proposal
