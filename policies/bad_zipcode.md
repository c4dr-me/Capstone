---
policy_id: POL-ZIP-001
title: Bad Zipcode Resolution Policy
exception_type: BAD_ZIPCODE
version: "1.0"
responsible_team: Payment Validation
default_severity: LOW
recommended_queue: Payment Validation
human_approval_required: false
sla_hours: 24
---

# Bad Zipcode Resolution Policy

## Exception Definition {#exception-definition}

The transaction was declined because the billing ZIP or postal code submitted did not
match the address verification data on file for the card. This is an address-verification
mismatch, not a card-security or funding issue.

## Default Severity {#default-severity}

`LOW`. A ZIP mismatch is usually a data-entry issue and rarely indicates card compromise
on its own.

## Responsible Team {#responsible-team}

`Payment Validation`. This team owns billing-detail correction workflows.

## Evidence Required {#evidence-required}

- Merchant category and state, when available.
- Transaction channel.
- Whether the case is a multi-error case.

## Recommended Action {#recommended-action}

Prompt the customer to confirm and correct the billing ZIP or postal code associated
with the card, then allow a normal resubmission through the standard checkout flow.

## Prohibited Action {#prohibited-action}

- Do not override address verification to force the transaction through.
- Do not infer or auto-fill a billing address on the customer's behalf.

## Human Approval Requirement {#human-approval-requirement}

Not required for the standard correct-and-resubmit action. Approval is required only if
the severity engine escalates the case to `HIGH` or `CRITICAL`.

## SLA {#sla}

24 hours from case creation to customer notification.

## Escalation Rule {#escalation-rule}

Escalate to `Payment Operations Manager` if the transaction amount is at or above the
high-value threshold used by the severity engine, or if the case is a multi-error case.
