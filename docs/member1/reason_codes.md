# Member 1 reason codes and citations

| Code | Meaning |
|---|---|
| `UNSUPPORTED_ACTION` | Action is outside the supported hackathon matrix. |
| `CASE_CONTEXT_MISMATCH` | Asserted facts differ from the governed case source. |
| `INSUFFICIENT_PERMISSION` | Role, queue, or proposing-agent authority does not intersect. |
| `FRAUD_CONTEXT_PRESENT` | Fraud `Yes` blocks every retry action. |
| `RETRY_LIMIT_REACHED` | At least one retry execution is already recorded. |
| `INELIGIBLE_EXCEPTION_TYPE` | Retry is limited to an exact Technical Glitch case. |
| `FRAUD_STATUS_UNKNOWN` | `Unknown` is preserved and requires manager review. |
| `HIGH_VALUE` | Absolute amount is at least $250. |
| `LIVE_RETRY_REQUIRES_APPROVAL` | `RETRY_PAYMENT` is never autonomous. |
| `SANDBOX_ONLY` | The action has no external financial effect. |
| `ESCALATION_PERMITTED` | The scoped principal may escalate the case. |

Retry decisions cite `POL-TECH-001@1.0`; simulations additionally cite
`GOV-SIM-TECH-001@1.0`. An `ALLOW` is not an execution command and remains
subject to Member 3's backend kill switch.
