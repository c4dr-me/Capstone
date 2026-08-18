"""Fake agent adapter for Member 2 used by Member 3 integration tests."""
from __future__ import annotations

import uuid
from typing import Any, Dict


def investigate_exception(case: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deterministic ProposedAction for a Technical Glitch case."""
    exception_id = case.get("exception_id")
    proposal = {
        "proposal_id": f"PROP-{uuid.uuid4().hex[:8]}",
        "exception_id": exception_id,
        "agent_id": "resolveone-investigator-fake",
        "action": "SIMULATE_RETRY_PAYMENT",
        "reason_codes": ["TECHNICAL_GLITCH", "FIRST_RETRY"],
        "explanation": "Deterministic fake: eligible for sandbox retry.",
        "policy_id": "POL-TECH-001",
        "policy_version": "1.0",
        "citations": ["POL-TECH-001@1.0"],
        "confidence": 0.99,
    }
    return proposal
