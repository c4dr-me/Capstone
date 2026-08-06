---
policy_id: POL-BAL-001
title: Insufficient Balance Resolution Policy
exception_type: INSUFFICIENT_BALANCE
version: "1.0"
responsible_team: Customer Payment Support
default_severity: LOW
recommended_queue: Customer Payment Support
human_approval_required: false
sla_hours: 24
---

# Insufficient Balance Resolution Policy

## Exception Definition {#exception-definition}

The transaction was declined because the available balance or available credit on the
card was lower than the requested transaction amount at the time of authorization. This
is a customer-funds condition, not a card defect or a system fault.

## Default Severity {#default-severity}

`LOW`. The card and payment rails are functioning correctly; the customer simply needs
to fund the account or choose an alternate payment method. Severity may be escalated by
the deterministic severity engine (see `agent/severity.py`) when the transaction amount
is unusually high, the case has multiple concurrent errors, a fraud signal is present, or
the same card has repeated exceptions.

## Responsible Team {#responsible-team}

`Customer Payment Support`. This team owns customer-facing balance and funding
conversations and does not require payment-operations escalation for a routine decline.

## Evidence Required {#evidence-required}

- Transaction amount and currency.
- Masked card identifier and masked client identifier.
- Whether the error co-occurs with any other error code (`is_multi_error`).
- Fraud-context label, if available (`Yes`, `No`, or `Unknown`).

## Recommended Action {#recommended-action}

Notify the customer that the transaction could not be completed due to insufficient
funds or available credit, and request an alternate payment method or a top-up. No
retry of the original authorization should be attempted until funding is confirmed.

## Prohibited Action {#prohibited-action}

- Do not automatically retry the charge without confirmed new funding.
- Do not extend credit, waive a balance requirement, or adjust the account balance.
- Do not treat this exception as a fraud indicator on its own.

## Human Approval Requirement {#human-approval-requirement}

Not required for the standard notify-and-request-alternate-payment action. Approval
is required only if the case is escalated to `HIGH` or `CRITICAL` severity by the
severity engine (for example, a high-value transaction or a fraud-context flag).

## SLA {#sla}

24 hours from case creation to customer notification.

## Escalation Rule {#escalation-rule}

Escalate to `Payment Operations Manager` review if the same masked card produces three
or more insufficient-balance exceptions within the case dataset, or if the transaction
amount is at or above the high-value threshold used by the severity engine.
