# ResolveOne Agent Architecture (Member 2)

## Purpose

This document describes the agent, RAG, and evaluation layer built for
ResolveOne AI's Member 2 workstream, per `implementation_team_split.md`. It
reads exclusively from Member 1's published Gold product
(`data/processed/gold_exception_cases.parquet`) and exposes exactly one public
function, `investigate_exception(exception_id)`, for Member 3's application
to call.

## Scope boundary

Member 2 owns `policies/`, `agent/`, `tests/agent/`, `tests/evaluation/`, and
`tests/security/agent_*`. Member 2 never reads `data/raw/` — enforced by
[`tests/agent/test_evidence_boundary.py`](../tests/agent/test_evidence_boundary.py),
which statically scans every module under `agent/` for a raw-file or
raw-directory string literal, and never writes to any persistent case
database — that belongs to Member 3.

## End-to-end flow

```text
investigate_exception(exception_id)
        │
        ▼
validate_contract            agent/graph.py -> agent/evidence.py
        │  (required fields present, error_types values are known)
        ▼
fetch_evidence                agent/graph.py -> agent/evidence.py
        │  (evidence_record_ids, limitations)
        ▼
score_severity_and_queue      agent/severity.py, agent/routing.py
        │  (deterministic, rule-based — no model call)
        ▼
retrieve_policy                agent/retrieval.py -> agent/mdm.py -> agent/vector_store.py
        │  (MDM entity resolution -> golden policy -> pgvector similarity search)
        ▼
generate_recommendation        agent/graph.py
        │  (recommended_action assembled from the cited policy chunk, deterministic)
        ▼
verify_policy_and_safety       agent/policy_gate.py
        │  (independent re-check: restricted fields, prompt injection, prohibited actions)
        │  fails closed -> flow halts here if verification fails
        ▼
require_human_approval         agent/graph.py
        │  (marks that a human decision is required before any controlled action executes)
        ▼
record_and_route                agent/graph.py -> agent/tools.py -> agent/idempotency.py
        │  (audit trail, idempotent submit_for_human_approval)
        ▼
   structured result dict
```

Implemented in [`agent/graph.py`](../agent/graph.py) as a `langgraph.graph.StateGraph`
over the state schema in [`agent/state.py`](../agent/state.py). The public entry
point is [`agent/orchestrator.py`](../agent/orchestrator.py).

## Why no LLM call in the hot path

Severity, routing, and the recommended-action text are all deterministic —
composed from the golden policy chunk text and rule-based reason codes, with
no network call, no API key dependency, and fully reproducible test/demo
runs. This matches implementation.md section 8: *"severity and routing should
be deterministic and explainable. The LLM explains the outcome; it does not
invent or override the rule."* An LLM-phrasing step could be added later as an
optional post-processing pass over the already-verified recommendation
without changing the trust boundary.

## Deterministic severity and routing

See [`agent/severity.py`](../agent/severity.py) and
[`agent/routing.py`](../agent/routing.py). Base severity/queue per exception
type follows implementation.md section 8's table exactly. Escalation rules,
calibrated against the actual Gold dataset distribution (amount p90 ≈ $120,
p99 ≈ $240; per-card exception count p90 ≈ 3):

| Condition | Effect | Reason code |
|---|---|---|
| `amount >= $250` | severity +1 level | `HIGH_VALUE_TRANSACTION` |
| `is_multi_error` | severity +1 level | `MULTI_ERROR_CASE` |
| `fraud_label == "Yes"` | forced to `CRITICAL` | `FRAUD_CONTEXT_PRESENT` |
| `>=3` historical exceptions on the same masked card | severity +1 level | `REPEATED_EXCEPTIONS_ON_CARD` |

Severity never exceeds `CRITICAL`. Multi-error cases (comma-joined
`error_types`) use the highest-base-severity component error as the primary
type for both severity and routing — one shared tie-break rule instead of two
independently defined ones. A `fraud_label == "Yes"` case always routes to
`Fraud Analyst` regardless of the underlying error type.

## Controlled tools and the trust boundary

[`agent/tools.py`](../agent/tools.py) implements the nine controlled tools
from implementation.md section 9 behind a single `ToolGateway.call_tool()`
choke point, adapted from the reference course material's tool-gateway
pattern (allowlist, required-parameter check, approval gate on irreversible
actions, idempotency-key dedup, structured audit log). An agent cannot invent
a tool — anything outside `TOOL_REGISTRY` is denied.

The independent safety verifier, [`agent/policy_gate.py`](../agent/policy_gate.py),
re-checks every recommendation before it can reach an analyst: it scans for
restricted field names (`card_number`, `cvv`, `pin`, ...), scans all business
text (evidence fields and the recommended action itself) for prohibited-action
or injection patterns, and matches the recommended action against the
policy's own prohibited-action list. This is the **prompt-injection
defense**: business data (merchant category, card brand, etc.) is treated as
inert evidence, never as an instruction, and any attempt to smuggle an
instruction into a data field is caught here — see
[`tests/security/agent_prompt_injection_test.py`](../tests/security/agent_prompt_injection_test.py)
and the captured trace in
[`agent_trace_blocked_sensitive_field.json`](agent_trace_blocked_sensitive_field.json).

## Idempotency and replay protection

[`agent/idempotency.py`](../agent/idempotency.py) keys replay protection by
`case:<exception_id>` in Redis (with an in-process fallback if Redis is
briefly unavailable), so replaying the same failed-payment event through
`investigate_exception()` never produces a second `submit_for_human_approval`
audit event — the second call returns `replayed: true` with an identical
result. See
[`agent_trace_replay_idempotent.json`](agent_trace_replay_idempotent.json).

## Related documents

- [`POLICY_LIBRARY.md`](POLICY_LIBRARY.md) — the seven synthetic resolution policies.
- [`MDM_RAG.md`](MDM_RAG.md) — the MDM layer applied to policy retrieval.
- [`AGENT_TRACES.md`](AGENT_TRACES.md) — walkthroughs of the three captured traces.
- [`EVALUATION.md`](EVALUATION.md) — evaluation methodology and results.
