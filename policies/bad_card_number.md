---
policy_id: POL-CARDNUM-001
title: Bad Card Number Resolution Policy
exception_type: BAD_CARD_NUMBER
version: "1.0"
responsible_team: Payment Validation
default_severity: MEDIUM
recommended_queue: Payment Validation
human_approval_required: false
sla_hours: 24
---

# Bad Card Number Resolution Policy

## Exception Definition {#exception-definition}

The transaction was declined because the card number submitted at checkout failed
validation (for example, a mistyped digit or an invalid check-digit result). This
indicates a data-entry or data-formatting issue rather than a card-security event.

## Default Severity {#default-severity}

`MEDIUM`. The underlying card is not necessarily compromised, but the transaction cannot
be completed until correct card details are supplied.

## Responsible Team {#responsible-team}

`Payment Validation`. This team owns checkout data-entry and formatting-validation
issues.

## Evidence Required {#evidence-required}

- Transaction channel (swipe, chip, or online) to distinguish entry method.
- Merchant category and whether the case is a multi-error case.
- Fraud-context label, if available.

## Recommended Action {#recommended-action}

Prompt the customer or merchant integration to re-enter and correctly submit the payment
card details, then allow a normal resubmission through the standard checkout flow.

## Prohibited Action {#prohibited-action}

- Do not guess, auto-correct, or infer a "likely" card number on the customer's behalf.
- Do not store or log the attempted invalid card number anywhere in the case record.
- Do not treat the mismatch as evidence of fraud without a corroborating signal.

## Human Approval Requirement {#human-approval-requirement}

Not required for the standard correct-and-resubmit action. Approval is required only if
the severity engine escalates the case to `HIGH` or `CRITICAL`.

## SLA {#sla}

24 hours from case creation to customer or merchant notification.

## Escalation Rule {#escalation-rule}

Escalate to `Card Security Review` if repeated bad-card-number attempts occur on the same
masked card in a short window, which can indicate card-testing activity.
