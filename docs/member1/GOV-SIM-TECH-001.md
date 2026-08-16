# GOV-SIM-TECH-001 v1.0 — Technical-Glitch Simulation Governance

Status: active for the ResolveOne hackathon sandbox.

`SIMULATE_RETRY_PAYMENT` is permitted only as a bounded sandbox operation. It
must not connect to, invoke, or mutate a production payment gateway or financial
ledger. It has no external financial effect.

Eligibility is evaluated deterministically from governed case facts and recorded
execution history. A Technical Glitch with fraud `No`, absolute amount below
$250, and no prior retry may be allowed. Fraud `Unknown` or an amount of at least
$250 requires Operations Manager approval. Fraud `Yes`, another exception type,
or a prior retry is denied.

An `ALLOW` decision is necessary but not sufficient for execution. Member 3 owns
the kill switch and may finalize the receipt as `AUTONOMY_DISABLED` without an
execution attempt.
