# ResolveOne

ResolveOne is a governed payment-exception operations workspace. It combines a Bronze–Silver–Gold data pipeline, a deterministic LangGraph investigation agent, policy retrieval through PostgreSQL and pgvector, and a human-gated Streamlit interface.

The current Gold product contains **211,393 exception cases** at one row per payment exception. All **11 published data-quality checks pass**, duplicate exception IDs are rejected, and the UI exposes masked identifiers only.

## What is included

- **Exception Queue** — search and prioritize real Gold cases by severity, type, queue, and decision state.
- **Case Investigation** — inspect masked evidence, card history, lineage, and explainable reason codes.
- **ResolveOne Agent + Policy RAG** — run the public `investigate_exception()` workflow from the UI.
- **Recommendation & Approval** — review cited policy guidance and record a required human decision.
- **Audit & Metrics** — inspect persisted decisions, runtime events, measured distributions, provenance, and pipeline quality.
- **Governance controls** — deterministic severity/routing, policy gating, prohibited-field checks, prompt-injection defense, and replay protection.

## Architecture

```text
Source data / BigQuery
        |
        v
Bronze -> Silver -> Gold Parquet
                       |
             +---------+----------+
             |                    |
             v                    v
      Streamlit workspace   LangGraph agent
             |                    |
             |             MDM policy profile
             |                    |
             |            PostgreSQL + pgvector
             |                    |
             +------ cited recommendation
                       |
                human approval
                       |
               decision + audit event
```

The agent hot path is deterministic: severity, routing, and recommended action are derived from governed evidence and approved policy content. The agent does not execute retries, refunds, reversals, balance changes, or card/account actions.

## Repository layout

```text
agent/       LangGraph workflow, retrieval, safety, routing, and evaluation
data/        Local raw/processed data products (ignored by Git)
docs/        Architecture, lineage, policy, evaluation, GCP, and runbook docs
policies/    Approved payment-exception policy documents
scripts/     GCP upload, BigQuery transformation, and Gold validation scripts
styles/      Streamlit design system
tests/       Agent, evaluation, security, and UI tests
utils/       Gold adapter, agent adapter, and decision/audit persistence
app.py       Main four-screen Streamlit application
```

## Prerequisites

- Python 3.12
- The published Gold file at `data/processed/gold_exception_cases.parquet`
- PostgreSQL with pgvector for live policy retrieval
- Redis for persistent replay protection

PostgreSQL and Redis are optional for viewing the UI. If pgvector is unavailable, the interface clearly labels the result as an **approved-policy deterministic fallback** and does not report a retrieval confidence score.

## Quick start on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r agent\requirements.txt
python -m pip install streamlit plotly
```

Point the application at the Gold product if it is stored elsewhere:

```powershell
$env:RESOLVEONE_GOLD_PARQUET = "E:\path\to\gold_exception_cases.parquet"
```

Launch the workspace:

```powershell
streamlit run app.py
```

Open `http://localhost:8501`. The default selected case is a real Technical Glitch exception so the Agent + RAG workflow is immediately demonstrable.

## Quick start on Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r agent/requirements.txt
python -m pip install streamlit plotly
streamlit run app.py
```

## Enable live Agent + RAG retrieval

Set the PostgreSQL connection string, enable pgvector, and build the governed policy index:

```powershell
$env:RESOLVEONE_PG_DSN = "dbname=resolveone user=resolveone password=change-me host=localhost port=5432"
psql -d resolveone -c "CREATE EXTENSION IF NOT EXISTS vector;"
python -m agent.build_index
```

Redis defaults to `localhost:6379/0`. Override it when needed:

```powershell
$env:RESOLVEONE_REDIS_HOST = "localhost"
$env:RESOLVEONE_REDIS_PORT = "6379"
$env:RESOLVEONE_REDIS_DB = "0"
```

The UI calls the agent through:

```python
from agent.orchestrator import investigate_exception

result = investigate_exception("EXC-7475516")
```

The workflow validates evidence, calculates deterministic severity and routing, resolves the golden policy profile, retrieves approved policy chunks, verifies safety, requires human approval, and returns a structured recommendation with citations.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `RESOLVEONE_GOLD_PARQUET` | `data/processed/gold_exception_cases.parquet` | Governed Gold data product |
| `DATA_PROCESSED_GOLD` | same as above | Alternate Gold-path variable used by the UI |
| `RESOLVEONE_POLICIES_DIR` | `policies/` | Approved policy source directory |
| `RESOLVEONE_PG_DSN` | local `labuser_db` socket | PostgreSQL/pgvector connection |
| `RESOLVEONE_REDIS_HOST` | `localhost` | Redis host |
| `RESOLVEONE_REDIS_PORT` | `6379` | Redis port |
| `RESOLVEONE_REDIS_DB` | `0` | Redis database |
| `RESOLVEONE_RUNTIME_DB` | `data/runtime/resolveone_runtime.db` | Local decision/audit SQLite path |
| `GCP_PROJECT_ID` | required by GCP scripts | Google Cloud project ID |
| `BQ_DATASET_ID` | `resolveone` | BigQuery dataset |

See [`.env.example`](.env.example) for the GCP and data-pipeline variables. The scripts read environment variables directly; load them into your shell before running a script.

## Testing

Run the self-contained UI/data tests:

```powershell
python -m pytest tests\ui -q
```

Run the full agent, retrieval, evaluation, and security suite after PostgreSQL/pgvector and Redis are available:

```powershell
python -m pytest tests\agent tests\evaluation tests\security -v
```

Validate the published Gold product:

```powershell
python scripts\validate_gold.py
```

## Data and privacy boundary

The application reads only the approved Gold product. It does not expose raw client IDs, raw card IDs, card numbers, CVV, PIN, address, latitude, or longitude. `Unknown` fraud status remains distinct from `No` and must not be interpreted as a non-fraud prediction.

Local analyst decisions are stored in SQLite for capstone/demo use. The production target remains PostgreSQL with authenticated analyst identity and production-grade access controls.

## Documentation

- [Implementation specification](implementation.md)
- [Agent architecture](docs/AGENT_ARCHITECTURE.md)
- [MDM applied to RAG](docs/MDM_RAG.md)
- [Policy library](docs/POLICY_LIBRARY.md)
- [Agent evaluation](docs/EVALUATION.md)
- [Agent traces](docs/AGENT_TRACES.md)
- [Gold data handoff](docs/README_DATA.MD)
- [Operational runbook](docs/RUNBOOK.md)
- [GCP setup and production guidance](docs/gcp/README.md)

## Current runtime behavior

- With PostgreSQL/pgvector online: the UI displays the LangGraph result with live policy citations and retrieval confidence.
- Without PostgreSQL/pgvector: the same UI remains usable and explicitly displays the deterministic approved-policy fallback.
- Every controlled decision requires an analyst reason and creates a linked audit event.
- No controlled payment or account action is executed by the Streamlit application.
