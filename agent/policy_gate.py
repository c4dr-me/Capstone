"""Independent policy and safety verifier — the trust-boundary enforcement
point described in implementation.md section 9 and section 11.

This module is the single place that decides whether a generated
recommendation is allowed to reach an analyst. It is deliberately independent
of the recommendation-generation code path: `verify_recommendation` re-derives
its own judgment from the golden policy record and the evidence, rather than
trusting flags set upstream.

Prompt-injection defense: every piece of business data (error text, merchant
category, card brand, etc.) is treated as inert evidence, never as an
instruction. This module never executes or interprets free text as a command;
it only pattern-matches known prohibited-action phrases and restricted-field
names for detection and blocking purposes.
"""

import re
from dataclasses import dataclass, field

RESTRICTED_FIELD_NAMES = {"card_number", "cvv", "cvv2", "full_card_number", "pin"}

PROHIBITED_ACTION_PATTERNS = [
    re.compile(r"\bretry\b.{0,30}\bwithout\b.{0,30}\bapproval\b", re.IGNORECASE),
    re.compile(r"\bignore\b.{0,30}\b(previous|prior|above)\b.{0,20}\binstructions?\b", re.IGNORECASE),
    re.compile(r"\breveal\b.{0,20}\b(cvv|pin|card number)\b", re.IGNORECASE),
    re.compile(r"\bdisclose\b.{0,20}\b(cvv|pin|card number)\b", re.IGNORECASE),
    re.compile(r"\b(refund|reverse|block the card|close the account)\b", re.IGNORECASE),
    re.compile(r"\bextend credit\b|\bwaive\b.{0,20}\bbalance\b", re.IGNORECASE),
    re.compile(r"\bbypass\b.{0,20}\bapproval\b", re.IGNORECASE),
]

UNAUTHORIZED_TOOL_PATTERN = re.compile(
    r"\b(drop table|delete from|update .* set|;\s*--|exec\(|os\.system)\b", re.IGNORECASE
)


@dataclass
class GateResult:
    passed: bool
    reason: str
    blocked_fields: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


def scan_for_restricted_fields(payload: dict) -> list[str]:
    return sorted(RESTRICTED_FIELD_NAMES & {str(k).lower() for k in payload.keys()})


def scan_text_for_injection(text: str) -> list[str]:
    if not text:
        return []
    hits = []
    for pattern in PROHIBITED_ACTION_PATTERNS:
        if pattern.search(text):
            hits.append(f"prohibited-action pattern matched: {pattern.pattern}")
    if UNAUTHORIZED_TOOL_PATTERN.search(text):
        hits.append("unauthorized tool/SQL pattern matched in business text")
    return hits


def verify_recommendation(
    recommended_action: str,
    prohibited_action_text: str,
    evidence: dict,
) -> GateResult:
    """Independent re-check of recommendation *content* before it is allowed
    to be returned to an analyst — restricted fields, prompt injection, and
    prohibited-action matches. This gate judges what is being recommended; it
    does not itself grant or check approval. Approval enforcement for any
    tool call that would execute a controlled action happens separately, in
    the tool registry (see `agent/tools.py`), which is the correct trust
    boundary: recommending a retry is safe to describe, executing one is not.

    Fails closed: any ambiguity or violation results in `passed=False`.
    """
    violations: list[str] = []

    blocked_fields = scan_for_restricted_fields(evidence)
    if blocked_fields:
        violations.append(f"evidence contains restricted fields: {blocked_fields}")

    injection_hits = scan_text_for_injection(recommended_action)
    if injection_hits:
        violations.extend(injection_hits)

    for field_name, field_value in evidence.items():
        if isinstance(field_value, str):
            injection_hits = scan_text_for_injection(field_value)
            if injection_hits:
                violations.append(f"business field '{field_name}' matched prohibited pattern")

    if prohibited_action_text:
        recommended_lower = recommended_action.lower()
        for line in prohibited_action_text.splitlines():
            fragment = line.strip("- ").strip().rstrip(".").lower()
            for prefix in ("do not ", "does not ", "not "):
                if fragment.startswith(prefix):
                    fragment = fragment[len(prefix):]
                    break
            if fragment and fragment in recommended_lower:
                violations.append(f"recommended action matches a prohibited action: '{fragment}'")

    if violations:
        return GateResult(
            passed=False,
            reason="; ".join(violations),
            blocked_fields=blocked_fields,
            violations=violations,
        )

    return GateResult(passed=True, reason="no violations detected", blocked_fields=[], violations=[])
