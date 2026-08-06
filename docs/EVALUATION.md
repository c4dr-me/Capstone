# Agent, RAG, and Security Evaluation

## Methodology

Run via `python -m agent.evaluation` (source:
[`agent/evaluation.py`](../agent/evaluation.py)). Results are written to
[`agent_evaluation_results.json`](agent_evaluation_results.json). All numbers
below are measured against the real Gold dataset
(`data/processed/gold_exception_cases.parquet`, 211,393 rows), not invented,
per implementation.md section 15's "Metrics are measured instead of
invented" requirement.

| Metric group | Method |
|---|---|
| Retrieval | For each of the 7 canonical exception types, call `retrieve_resolution_policy()` with a representative raw error code and check whether the golden policy_id is the top-1 / within top-3 result. |
| Groundedness & citations | Sample 30 real Gold cases per error type (210 total), run `investigate_exception()`, and check that every citation resolves to a real policy chunk and the recommended action text is contained in the cited `#recommended-action` chunk. |
| Routing | Same 210-case sample: compare `recommended_queue` against the queue independently derived from `RECOMMENDED_QUEUE_BY_TYPE` and the fraud-context override. |
| Latency | 100 randomly sampled real exception_ids, wall-clock time per `investigate_exception()` call. |
| Security | Adversarial probes: invented tool names against `TOOL_REGISTRY`, approval-required tools called without an approval token, a scan of recommendation output for restricted field names across 50 sampled cases, 10 cases replayed twice to check for duplicate non-replayed submissions, and 4 known prompt-injection phrases against the safety-gate text scanner. |
| Upstream data quality | Reads Member 1's `quality_results.json` directly — Member 2 does not re-derive Gold-layer quality claims. |

## Results (most recent run)

| Metric | Result | Target (implementation.md §15) | Met? |
|---|---:|---:|:---:|
| Top-1 retrieval accuracy | 100% | ≥ 90% | ✅ |
| Top-3 retrieval accuracy | 100% | — | ✅ |
| Citation completeness | 100% | 100% | ✅ |
| Recommendation groundedness rate | 100% | — | ✅ |
| Unsupported recommendation rate | 0% | — | ✅ |
| Routing accuracy | 100% | ≥ 90% | ✅ |
| Unauthorized tool calls executed | 0 / 3 attempts | 0 | ✅ |
| Approval-bypass count | 0 / 1 attempt | 0 | ✅ |
| Sensitive-field leakage count | 0 / 50 sampled cases | 0 | ✅ |
| Duplicate cases after replay | 0 / 10 replayed | 0 | ✅ |
| Prompt-injection success count | 0 / 4 known payloads | 0 | ✅ |
| p50 / p95 / max latency | 187 ms / 6.3 s / 12.5 s | — | ⚠ see limitation below |

Full machine-readable output: [`agent_evaluation_results.json`](agent_evaluation_results.json).

## Known limitation: latency tail

The p95/max latency figures are dominated by opening a fresh `psycopg2`
connection to Postgres on every `retrieve_resolution_policy()` call inside
`investigate_exception()` (see `agent/vector_store.get_connection()` /
`agent/retrieval.py`). This is acceptable for a capstone demo processing one
case at a time, but a production version should hold a pooled connection
(e.g. `psycopg2.pool.ThreadedConnectionPool`) across calls — that change is
isolated to `agent/vector_store.py` and would not affect any other module's
interface.

## Why 100% on several metrics is expected, not suspicious

Retrieval, groundedness, and routing are 100% because the underlying logic is
deterministic and the golden-policy-scoped retrieval in
[`MDM_RAG.md`](MDM_RAG.md) makes it structurally impossible for a known error
code to retrieve the wrong policy — this is a rules system with an
explainability layer, not a probabilistic classifier, so near-100% on these
metrics reflects correct behavior rather than overfitting. The security
metrics are 100% because every attack is checked against an explicit
allowlist or pattern set enumerated in `agent/tools.py` and
`agent/policy_gate.py` — they demonstrate the *known* attacks in the test
suite are blocked, not that the system is unconditionally secure against
attacks outside that set.

## How to reproduce

```bash
python -m agent.build_index      # (re)builds the pgvector policy index
python -m pytest tests/agent tests/evaluation tests/security -v
python -m agent.evaluation
```
