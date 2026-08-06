"""calculate_recommended_queue(exception_id) — deterministic queue routing.

Queue assignment follows implementation.md section 8's table exactly. The
severity engine already selects the highest-severity component error as
`primary_exception_type` for multi-error cases, so routing simply follows
that same primary type — one consistent tie-break rule shared by severity and
routing, rather than two independent (and potentially conflicting) rules.
"""

from agent.severity import SeverityResult, calculate_exception_severity

RECOMMENDED_QUEUE_BY_TYPE = {
    "INSUFFICIENT_BALANCE": "Customer Payment Support",
    "BAD_PIN": "Card Support",
    "TECHNICAL_GLITCH": "Payment Operations",
    "BAD_CARD_NUMBER": "Payment Validation",
    "BAD_EXPIRATION": "Card Support",
    "BAD_CVV": "Card Security Review",
    "BAD_ZIPCODE": "Payment Validation",
}

ESCALATED_QUEUE_OVERRIDE = {
    "CRITICAL": "Fraud Analyst",
}


def calculate_recommended_queue(
    exception_id: str, severity_result: SeverityResult | None = None
) -> tuple[str, SeverityResult]:
    severity_result = severity_result or calculate_exception_severity(exception_id)

    if "FRAUD_CONTEXT_PRESENT" in severity_result.reason_codes:
        queue = ESCALATED_QUEUE_OVERRIDE["CRITICAL"]
    else:
        queue = RECOMMENDED_QUEUE_BY_TYPE[severity_result.primary_exception_type]

    return queue, severity_result
