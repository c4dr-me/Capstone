# Synthetic Resolution Policy Library

## Purpose

Internal bank resolution procedures are not present in the public Financial
Transactions Dataset, so `policies/` contains seven small synthetic policy
documents — one per error type observed in Gold's `error_types` column. Each
is a governance artifact, not marketing copy: it exists to be retrieved,
cited, and enforced by the agent.

## Format

Every policy file is YAML frontmatter followed by nine `## Heading {#anchor}`
sections. The frontmatter declares the policy's identity and golden-record
fields:

```yaml
---
policy_id: POL-TECH-001
title: Technical Glitch Resolution Policy
exception_type: TECHNICAL_GLITCH
version: "1.0"
responsible_team: Payment Operations
default_severity: HIGH
recommended_queue: Payment Operations
human_approval_required: true
sla_hours: 4
---
```

The nine sections, each independently retrievable and citable, are:
Exception Definition, Default Severity, Responsible Team, Evidence Required,
Recommended Action, Prohibited Action, Human Approval Requirement, SLA, and
Escalation Rule — matching the required fields listed in
`implementation_team_split.md` section 4. Anchors follow kebab-case
(`{#recommended-action}`), so a citation looks like
`technical_glitch.md#recommended-action`.

Parsed by [`agent/policy_library.py`](../agent/policy_library.py) into
`PolicyChunk` objects, one per section, each carrying its own `chunk_id`
(`policy_id:version:anchor`) and `content_hash` (SHA-256 of the section text).

## The seven policies

| File | policy_id | exception_type | default_severity | responsible_team | human_approval_required |
|---|---|---|---|---|---|
| `insufficient_balance.md` | POL-BAL-001 | INSUFFICIENT_BALANCE | LOW | Customer Payment Support | false |
| `bad_pin.md` | POL-PIN-001 | BAD_PIN | MEDIUM | Card Support | true |
| `technical_glitch.md` | POL-TECH-001 | TECHNICAL_GLITCH | HIGH | Payment Operations | true |
| `bad_card_number.md` | POL-CARDNUM-001 | BAD_CARD_NUMBER | MEDIUM | Payment Validation | false |
| `bad_expiration.md` | POL-EXP-001 | BAD_EXPIRATION | MEDIUM | Card Support | false |
| `bad_cvv.md` | POL-CVV-001 | BAD_CVV | HIGH | Card Security Review | true |
| `bad_zipcode.md` | POL-ZIP-001 | BAD_ZIPCODE | LOW | Payment Validation | false |

Every policy's Prohibited Action section is enforced at runtime by
[`agent/policy_gate.py`](../agent/policy_gate.py) — for example,
`technical_glitch.md`'s "Do not retry more than once without a documented
service-health confirmation" is checked against the generated recommendation
text before it is ever returned.

## Versioning

All seven policies are currently at version `1.0`. A future revision (e.g.
tightening the CVV-mismatch escalation threshold) would bump `version` in the
frontmatter; the MDM survivorship rule in
[`agent/mdm.py`](../agent/mdm.py) — see [`MDM_RAG.md`](MDM_RAG.md) — ensures
retrieval always resolves to the highest declared version, never a stale one.
