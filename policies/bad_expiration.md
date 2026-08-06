---
policy_id: POL-EXP-001
title: Bad Expiration Resolution Policy
exception_type: BAD_EXPIRATION
version: "1.0"
responsible_team: Card Support
default_severity: MEDIUM
recommended_queue: Card Support
human_approval_required: false
sla_hours: 24
---

# Bad Expiration Resolution Policy

## Exception Definition {#exception-definition}

The transaction was declined because the expiration date submitted did not match the
card on file, or the card itself has expired. This is typically a stale-data or
expired-card condition rather than a security event.

## Default Severity {#default-severity}

`MEDIUM`. The customer can usually resolve this by updating card details or requesting a
replacement card.

## Responsible Team {#responsible-team}

`Card Support`. This team can confirm the card's true expiration status and issue a
replacement if the card has genuinely expired.

## Evidence Required {#evidence-required}

- Whether the card is flagged as expired versus a data-entry mismatch.
- Transaction channel and merchant category.
- Whether the case is a multi-error case.

## Recommended Action {#recommended-action}

If the card has genuinely expired, initiate a replacement-card request and notify the
customer. If the expiration date was mistyped, prompt for correct re-entry through the
standard checkout flow.

## Prohibited Action {#prohibited-action}

- Do not override or bypass expiration validation to force the transaction through.
- Do not issue a replacement card without confirming the current card's true status.

## Human Approval Requirement {#human-approval-requirement}

Not required for the standard replacement or correct-and-resubmit action. Approval is
required only if the severity engine escalates the case to `HIGH` or `CRITICAL`.

## SLA {#sla}

24 hours from case creation to customer notification or replacement-card initiation.

## Escalation Rule {#escalation-rule}

Escalate to `Payment Operations Manager` if the transaction amount is at or above the
high-value threshold used by the severity engine.
