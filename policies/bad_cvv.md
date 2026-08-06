---
policy_id: POL-CVV-001
title: Bad CVV Resolution Policy
exception_type: BAD_CVV
version: "1.0"
responsible_team: Card Security Review
default_severity: HIGH
recommended_queue: Card Security Review
human_approval_required: true
sla_hours: 8
---

# Bad CVV Resolution Policy

## Exception Definition {#exception-definition}

The transaction was declined because the card verification value (CVV) submitted did not
match the value on record. A CVV mismatch is a stronger security signal than most other
decline reasons because the CVV is not printed on card-reading equipment and is intended
to prove possession of the physical card.

## Default Severity {#default-severity}

`HIGH`. CVV mismatches carry elevated card-testing and unauthorized-use risk relative to
other exception types.

## Responsible Team {#responsible-team}

`Card Security Review`. This team is authorized to evaluate security-sensitive decline
patterns before any retry is permitted.

## Evidence Required {#evidence-required}

- Count of CVV-mismatch exceptions on the same masked card in the case dataset.
- Fraud-context label, if available.
- Transaction channel and whether the case is a multi-error case.

## Recommended Action {#recommended-action}

Hold the transaction for security review and require successful step-up verification
before any retry is considered. The full CVV value must never be retrieved, displayed,
or logged as part of this review — only the fact of a mismatch is evidence.

## Prohibited Action {#prohibited-action}

- Do not access, display, or store the actual CVV value at any point in the workflow.
- Do not permit an automatic or unverified retry.
- Do not treat a single mismatch alone as confirmed fraud without corroborating signals.

## Human Approval Requirement {#human-approval-requirement}

Required. Any retry or account action following a CVV mismatch requires analyst
approval after verification evidence is reviewed.

## SLA {#sla}

8 hours from case creation to security-review outcome.

## Escalation Rule {#escalation-rule}

Escalate to `Fraud Analyst` review if three or more CVV-mismatch exceptions occur on the
same masked card, or if a fraud-context label of `Yes` is present.
