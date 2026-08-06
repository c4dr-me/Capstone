---
policy_id: POL-PIN-001
title: Bad PIN Resolution Policy
exception_type: BAD_PIN
version: "1.0"
responsible_team: Card Support
default_severity: MEDIUM
recommended_queue: Card Support
human_approval_required: true
sla_hours: 12
---

# Bad PIN Resolution Policy

## Exception Definition {#exception-definition}

The transaction was declined because the PIN entered at the point of interaction did not
match the PIN on record for the card. This may indicate a forgotten PIN, a card-reader
issue, or an attempted unauthorized use of the card.

## Default Severity {#default-severity}

`MEDIUM`. A single bad-PIN event is usually benign, but repeated attempts on the same
card raise the likelihood of unauthorized use, so the severity engine escalates on
repetition or a fraud-context signal.

## Responsible Team {#responsible-team}

`Card Support`. This team can perform identity-verified PIN resets and step-up
verification.

## Evidence Required {#evidence-required}

- Count of PIN-decline exceptions for the same masked card in the case dataset.
- Fraud-context label, if available.
- Whether the case is a multi-error case (co-occurring with another decline reason).

## Recommended Action {#recommended-action}

Route the case for step-up identity verification. If verification succeeds, a
controlled PIN reset or a single controlled retry may be offered; if verification
fails or cannot be completed, the case escalates to Card Security Review.

## Prohibited Action {#prohibited-action}

- Do not perform an automatic, unverified retry of the transaction.
- Do not reset or reveal a PIN without successful identity verification.
- Do not disclose the current PIN under any circumstance.

## Human Approval Requirement {#human-approval-requirement}

Required. A controlled retry or PIN reset is a security-sensitive action and must be
approved by an analyst after step-up verification evidence is reviewed.

## SLA {#sla}

12 hours from case creation to verification outreach.

## Escalation Rule {#escalation-rule}

Escalate to `Card Security Review` if three or more bad-PIN exceptions occur on the same
masked card, or if a fraud-context label of `Yes` is present.
