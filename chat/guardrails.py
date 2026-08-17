"""AI guardrails: prompt injection, PII field blocking, action validation."""

import re
from typing import Literal

from contracts.enums import Action


def detect_prompt_injection(text: str) -> bool:
    """Detect common prompt injection patterns.

    Returns:
        True if injection-like text detected (ignore policy, system, override, etc.)
    """
    patterns = [
        r"ignore\s+(all\s+)?polic",
        r"system\s+prompt",
        r"forget\s+(all\s+)?instructions",
        r"override\s+(all\s+)?rules",
        r"you\s+are\s+now",
        r"pretend\s+you\s+are",
        r"act\s+like\s+you",
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)


def detect_restricted_field_request(text: str) -> bool:
    """Detect requests for sensitive/restricted fields.

    Returns:
        True if PII/sensitive field requested (card number, CVV, PIN, customer records, etc.)
    """
    patterns = [
        r"full\s+card",
        r"complete\s+card",
        r"card\s+number",
        r"cvv|cvc|cvv2",
        r"pin\s+code",
        r"secret",
        r"password",
        r"ssn|social\s+security",
        r"unmasked",
        r"raw\s+data",
        r"encryption\s+key",
        r"signing\s+key",
        r"database\s+credential",
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)


def validate_action_allowlist(action: Action) -> tuple[bool, str | None]:
    """Validate that an action is in the supported allowlist.

    Returns:
        (is_valid, reason_code_if_invalid)
    """
    allowed = {Action.SIMULATE_RETRY_PAYMENT, Action.ESCALATE}
    if action in allowed:
        return True, None
    return False, "UNSUPPORTED_ACTION"


def validate_citations(
    citations: tuple[str, ...], known_policy_ids: set[str] | None = None
) -> tuple[bool, str | None]:
    """Validate that citations are present and well-formed.

    Args:
        citations: tuple of citation strings, e.g. ("POL-TECH-001@1.0",)
        known_policy_ids: optional set of valid policy IDs to check against

    Returns:
        (is_valid, reason_code_if_invalid)
    """
    if not citations:
        return False, "MISSING_CITATIONS"

    for citation in citations:
        if "@" not in citation:
            return False, "INVALID_CITATION_FORMAT"
        parts = citation.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return False, "INVALID_CITATION_FORMAT"
        policy_id = parts[0]
        if known_policy_ids and policy_id not in known_policy_ids:
            return False, "UNKNOWN_POLICY_ID"

    return True, None


def run_guardrails(
    text: str, action: Action | None = None, citations: tuple[str, ...] | None = None
) -> tuple[bool, str | None]:
    """Run all guardrails on a user input and proposed action.

    Args:
        text: user's input text
        action: proposed action (optional)
        citations: proposed citations (optional)

    Returns:
        (passed, reason_code_if_blocked)

    Reason codes:
        - BLOCKED_POLICY_OVERRIDE: prompt injection detected
        - BLOCKED_SENSITIVE_FIELD: PII/sensitive field request detected
        - UNSUPPORTED_ACTION: action not in allowlist
        - MISSING_CITATIONS: no citations provided when required
        - INVALID_CITATION_FORMAT: citations malformed
    """
    if detect_prompt_injection(text):
        return False, "BLOCKED_POLICY_OVERRIDE"

    if detect_restricted_field_request(text):
        return False, "BLOCKED_SENSITIVE_FIELD"

    if action is not None:
        valid, reason = validate_action_allowlist(action)
        if not valid:
            return False, reason

    if citations is not None:
        valid, reason = validate_citations(citations)
        if not valid:
            return False, reason

    return True, None
