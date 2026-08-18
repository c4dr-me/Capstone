"""Fake AccessContext adapter used by Member 3 integration tests."""
from __future__ import annotations

from typing import Dict


def mint_access_context(session: Dict[str, str]) -> Dict[str, str]:
    return {"context_id": "CTX-FAKE", "user_id": session.get("user_id", "ops_01"), "canonical_role": session.get("role", "OPERATIONS_ANALYST" )}


def validate_access_context(context: Dict[str, str]) -> Dict[str, str]:
    # Pass-through fake validation
    if "context_id" not in context:
        context["context_id"] = "CTX-FAKE"
    return context
