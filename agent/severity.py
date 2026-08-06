"""calculate_exception_severity(exception_id) — deterministic severity scoring.

Severity and routing are rule-based and explainable, per implementation.md
section 8: "For the MVP, severity and routing should be deterministic and
explainable. The LLM explains the outcome; it does not invent or override the
rule." No model call is involved anywhere in this module.
"""

from dataclasses import dataclass

from agent.config import HIGH_VALUE_AMOUNT_THRESHOLD, REPEATED_EXCEPTIONS_THRESHOLD
from agent.evidence import get_exception_case, get_payment_profile
from agent.mdm import resolve_exception_type

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

BASE_SEVERITY_BY_TYPE = {
    "INSUFFICIENT_BALANCE": "LOW",
    "BAD_PIN": "MEDIUM",
    "TECHNICAL_GLITCH": "HIGH",
    "BAD_CARD_NUMBER": "MEDIUM",
    "BAD_EXPIRATION": "MEDIUM",
    "BAD_CVV": "HIGH",
    "BAD_ZIPCODE": "LOW",
}


@dataclass
class SeverityResult:
    exception_id: str
    primary_exception_type: str
    component_exception_types: list[str]
    base_severity: str
    final_severity: str
    reason_codes: list[str]


def _escalate(severity: str, levels: int = 1) -> str:
    idx = SEVERITY_ORDER.index(severity)
    return SEVERITY_ORDER[min(idx + levels, len(SEVERITY_ORDER) - 1)]


def _split_error_types(raw_error_types: str) -> list[str]:
    return [e.strip() for e in raw_error_types.split(",") if e.strip()]


def calculate_exception_severity(exception_id: str) -> SeverityResult:
    case = get_exception_case(exception_id)
    if case is None:
        raise ValueError(f"exception_id '{exception_id}' not found in Gold evidence")

    raw_types = _split_error_types(case["error_types"])
    canonical_types = [resolve_exception_type(t) for t in raw_types]
    canonical_types = [t for t in canonical_types if t is not None]
    if not canonical_types:
        raise ValueError(f"exception_id '{exception_id}' has no resolvable error types: {raw_types}")

    # Highest-base-severity component is primary, matching implementation.md's
    # multi-error tie-break: the most severe component error drives the case.
    primary_type = max(canonical_types, key=lambda t: SEVERITY_ORDER.index(BASE_SEVERITY_BY_TYPE[t]))
    base_severity = BASE_SEVERITY_BY_TYPE[primary_type]

    reason_codes = [primary_type]
    severity = base_severity

    if case["amount"] is not None and case["amount"] >= HIGH_VALUE_AMOUNT_THRESHOLD:
        severity = _escalate(severity)
        reason_codes.append("HIGH_VALUE_TRANSACTION")

    if bool(case["is_multi_error"]):
        severity = _escalate(severity)
        reason_codes.append("MULTI_ERROR_CASE")

    if case["fraud_label"] == "Yes":
        severity = "CRITICAL"
        reason_codes.append("FRAUD_CONTEXT_PRESENT")

    profile = get_payment_profile(case["masked_card_id"])
    if profile["historical_exception_count"] >= REPEATED_EXCEPTIONS_THRESHOLD:
        severity = _escalate(severity)
        reason_codes.append("REPEATED_EXCEPTIONS_ON_CARD")

    return SeverityResult(
        exception_id=exception_id,
        primary_exception_type=primary_type,
        component_exception_types=canonical_types,
        base_severity=base_severity,
        final_severity=severity,
        reason_codes=reason_codes,
    )
