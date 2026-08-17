"""Typed, proposal-only compatibility API for Member 2 investigations."""

import uuid
from typing import Any

from contracts.case import GovernedCase
from contracts.enums import Action
from chat.schemas import ProposedAction


def investigate_exception(case: GovernedCase | dict[str, Any]) -> ProposedAction:
    """Return a bounded proposal from governed evidence; never authorize or execute."""
    governed = GovernedCase.model_validate(case)
    if governed.exception_type.upper() == "TECHNICAL_GLITCH" and str(governed.fraud_label) == "No":
        action = Action.SIMULATE_RETRY_PAYMENT
        reasons = ("TECHNICAL_GLITCH", "GOVERNED_EVIDENCE")
        explanation = "A sandbox-only retry is proposed, subject to deterministic authorization."
    else:
        action = Action.ESCALATE
        reasons = ("GOVERNED_EVIDENCE", "ESCALATION")
        explanation = "The case is proposed for escalation; no execution is requested."
    return ProposedAction(
        proposal_id=f"PROP-{uuid.uuid4().hex[:8].upper()}", exception_id=governed.exception_id,
        agent_id="resolveone-investigator", action=action, reason_codes=reasons, explanation=explanation,
        policy_id="POL-TECH-001", policy_version="1.0", citations=("POL-TECH-001@1.0",), confidence=0.9,
    )