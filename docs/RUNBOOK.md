# Member 2 Runbook: Step-by-Step

This is the single place to run everything Member 2 built — from a clean
checkout to passing tests, a populated policy index, and a live
`investigate_exception()` call. It assumes Member 1's Gold output already
exists at `data/processed/gold_exception_cases.parquet` (it does, in this
repo — 211,393 rows, all quality checks passed).

## 0. What you need running

| Service | Check it's up | Notes |
|---|---|---|
| PostgreSQL 16+ with `pgvector` | `pg_lsclusters` shows `online` | Used for the policy vector index. |
| Redis | `redis-cli ping` → `PONG` | Used for idempotent replay protection; the agent falls back to an in-process set if Redis is briefly down. |
| Python 3.12 | `python3 --version` | This project was built and tested on 3.12.8. |

If PostgreSQL isn't running: `sudo service postgresql start`.
If Redis isn't running: `redis-server --daemonize yes`.

## 1. Install dependencies

```bash
cd /home/labuser/Desktop/Persistent_Folder/Capstone
pip install --user -r requirements.txt
```

This installs: `langgraph`, `langchain-core`, `pandas`, `pyarrow`, `numpy`,
`scikit-learn`, `joblib`, `pyyaml`, `psycopg2-binary`, `pgvector`, `redis`,
`pytest`. No API key is required anywhere in this stack — retrieval uses
local TF-IDF embeddings and every recommendation is generated deterministically.

## 2. Enable the pgvector extension (one time)

```bash
psql -U labuser -d labuser_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Safe to re-run — it's a no-op if the extension already exists. Uses your OS
user's peer-authenticated Postgres role (`labuser` on `labuser_db` in this
environment); override with the `RESOLVEONE_PG_DSN` environment variable if
your setup differs (see `agent/config.py`).

## 3. Build the policy index

```bash
python -m agent.build_index
```

This:
1. Parses all 7 files in `policies/` into citable chunks.
2. Builds the MDM golden policy profile (prints a summary — no `⚠` lines
   means no survivorship conflicts).
3. Fits a TF-IDF vectorizer over the policy text and saves it to
   `agent/artifacts/tfidf_vectorizer.joblib`.
4. Creates the `policy_chunks` table in Postgres (if it doesn't exist) and
   loads all chunk embeddings into it.

Re-run this any time a policy `.md` file changes.

## 4. Run the test suite

```bash
python -m pytest tests/agent tests/evaluation tests/security -v
```

Expect `61 passed`. This covers:
- `tests/agent/` — severity, routing, MDM/RAG, evidence-boundary (never
  touches `data/raw/`), and full end-to-end graph tests.
- `tests/evaluation/` — retrieval accuracy, citation/groundedness checks.
- `tests/security/` — prompt-injection, restricted-field blocking, and
  idempotent-replay tests.

## 5. Run the evaluation harness

```bash
python -m agent.evaluation
```

Prints and writes `docs/agent_evaluation_results.json` — retrieval accuracy,
groundedness, routing accuracy, latency percentiles, and security-probe
results, measured against the real Gold dataset. See
[`EVALUATION.md`](EVALUATION.md) for how to read the numbers.

## 6. Call the agent yourself

This is the one function Member 3's UI needs:

```python
from agent.orchestrator import investigate_exception

result = investigate_exception("EXC-7475516")   # any real exception_id from Gold
print(result)
```

To find a real `exception_id` to try:

```python
import pandas as pd
df = pd.read_parquet("data/processed/gold_exception_cases.parquet")
print(df[df["error_types"] == "Technical Glitch"].iloc[0]["exception_id"])
```

Or from the shell in one line:

```bash
python -c "
from agent.orchestrator import investigate_exception
import json
print(json.dumps(investigate_exception('EXC-7475516'), indent=2, default=str))
"
```

## 7. Live-demo path proof points

These map to `implementation.md` section 16's live demo steps and are already
captured under `docs/`:

| Demo step | Where to look |
|---|---|
| Run the LangGraph investigation, show policy + citation | [`agent_trace_technical_glitch_approved.json`](agent_trace_technical_glitch_approved.json) |
| Replay the event, prove no duplicate case | [`agent_trace_replay_idempotent.json`](agent_trace_replay_idempotent.json) |
| Request a prohibited sensitive field, show it blocked | [`agent_trace_blocked_sensitive_field.json`](agent_trace_blocked_sensitive_field.json) |
| Open the metrics | [`agent_evaluation_results.json`](agent_evaluation_results.json) |

To regenerate any of these live instead of reading the saved JSON, re-run the
capture snippets described in [`AGENT_TRACES.md`](AGENT_TRACES.md#reproducing-these-traces).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: No fitted vectorizer` | Step 3 hasn't been run yet | `python -m agent.build_index` |
| `psycopg2.OperationalError` connecting | Postgres not running, or wrong DSN | `sudo service postgresql start`; check `RESOLVEONE_PG_DSN` |
| `ModuleNotFoundError: No module named 'langgraph.graph'` | Only `langgraph-checkpoint`/`langgraph-prebuilt` were installed, not the core `langgraph` package | `pip install --user langgraph` |
| A retrieval test fails with the wrong `policy_id` | Policy index is stale (a `.md` file changed since the last build) | `python -m agent.build_index` |
| Idempotency-replay test behaves unexpectedly on repeat runs | Leftover Redis key from a prior manual run | `redis-cli --scan --pattern 'resolveone:agent:idempotency:*' \| xargs redis-cli del` |

## Environment variable overrides

All optional, all default to sensible local values (see `agent/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `RESOLVEONE_GOLD_PARQUET` | `data/processed/gold_exception_cases.parquet` | Path to Member 1's Gold output |
| `RESOLVEONE_POLICIES_DIR` | `policies/` | Policy markdown source directory |
| `RESOLVEONE_PG_DSN` | `dbname=labuser_db user=labuser host=/var/run/postgresql` | Postgres connection string |
| `RESOLVEONE_REDIS_HOST` / `_PORT` / `_DB` | `localhost` / `6379` / `0` | Redis connection |

## Does this expose what Member 3's UI needs?

Yes. `agent.orchestrator.investigate_exception(exception_id: str) -> dict` is
the exact function name and signature specified in
`implementation_team_split.md`'s Member 2 "Required output contract", and its
return value is a strict superset of the documented response schema:

```json
{
  "exception_id": "EXC-001",
  "severity": "HIGH",
  "recommended_queue": "Payment Operations",
  "recommended_action": "...",
  "reason_codes": ["TECHNICAL_GLITCH", "..."],
  "policy_id": "POL-TECH-001",
  "policy_version": "1.0",
  "citations": ["technical_glitch.md#recommended-action"],
  "confidence": 0.39,
  "approval_required": true,
  "evidence_record_ids": ["TXN-7475516"],
  "limitations": []
}
```

Three additional fields are included beyond the documented schema —
`blocked` (bool), `block_reason` (string or null), and `replayed` (bool).
These are additive, not breaking: Member 3's UI can ignore them entirely and
still be fully compatible with the documented contract, or use them to show
a "blocked" banner / "already submitted" state without needing any new call.
No documented field was renamed, removed, or changed in meaning.
