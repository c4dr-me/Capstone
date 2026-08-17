# ResolveOne 2.0

ResolveOne is a governed autonomous payment-exception control plane. It investigates failed-payment cases, retrieves approved policy, proposes bounded actions, applies deterministic authorization, safely simulates an eligible recovery, and preserves the complete decision path as a tamper-evident receipt and Neo4j lineage graph.

The core design principle is:

> **AI provides intelligence; deterministic enterprise controls retain authority.**

The hackathon innovation is the **Decision Twin**: a replayable representation of the case evidence, policy, identity, proposal, authorization, approval, execution attempt, outcome, and governance receipt.

## Current implementation status

This repository contains working components and an integration plan. The distinction matters:

| Capability | Current status | Notes |
| --- | --- | --- |
| Bronze–Silver–Gold data product | Working | 211,393 governed payment-exception cases; masked identifiers only |
| Existing operations UI (`app.py`) | Working, legacy workflow | Queue, evidence, deterministic agent/RAG, human form, local SQLite audit |
| Member 1 governance | Working | Signed access contexts, deterministic authorization, maker-checker approval, Neo4j receipts and lineage |
| Member 1 governance console | Working development harness | Real Neo4j backend with an interactive lineage graph |
| Member 2 deterministic agent | Working baseline | LangGraph, governed evidence, policy retrieval, routing and safety gate |
| Member 2 LLM proposals | Working with configured provider | Groq, OpenRouter, or Gemini structured proposals; missing or failed provider uses the labelled approved-policy fallback |
| Member 3 orchestration and sandbox execution | Integration task | Must combine Member 2 and Member 1 in the main UI and enforce the kill switch |
| Final single-URL judge workflow | Not complete yet | Member 3 owns this completion gate |

The focused governance console is not the final product UI. It exists so Member 1 can be tested independently against real Neo4j. The final demonstration must expose the complete workflow through the main Streamlit entry point without changing URLs.

## Target end-to-end workflow

```text
Synthetic payment exception
        ↓
Member 3 integration orchestrator
        ↓
Member 2 investigates evidence and retrieves policy
        ↓
Member 2 returns a grounded ProposedAction
        ↓
Member 1 validates identity and authoritative case facts
        ↓
Member 1 returns ALLOW / DENY / REQUIRE_APPROVAL
        ↓
Member 3 enforces the persisted kill switch
        ↓
SIMULATE_RETRY_PAYMENT executes in the sandbox when permitted
        ↓
Member 3 verifies the result
        ↓
Member 1 finalizes the tamper-evident receipt
        ↓
Member 3 displays status, evidence, metrics, receipt and lineage in the main UI
```

For the low-risk golden path, the synthetic event should trigger the entire sequence without manual **Authorize** or **Finalize** clicks. Human interaction remains mandatory for `REQUIRE_APPROVAL`, identity changes, and autonomy controls. `DENY` always stops automatically.

## Workstream ownership

| Member | Owns | Public responsibility |
| --- | --- | --- |
| Member 1 | Identity, access context, authorization, approvals, Neo4j, receipts and lineage | Decide whether a proposal may proceed and prove why |
| Member 2 | LangGraph investigation, Ask ResolveOne, policy RAG, LLM provider, proposals and AI guardrails | Understand the case and return a grounded answer or bounded proposal |
| Member 3 | Events, integration orchestrator, sandbox executor, kill switch, main UI and observability | Turn an authorized proposal into a safe, visible and verified outcome |

Member 3 is the accountable owner of the final visible workflow. Member 1 and Member 2 being complete means their real adapters and contracts are ready; it does not mean the integrated product is finished.

## AI agent and LLM providers

The current agent hot path is deterministic. It validates governed evidence, calculates severity and queue routing, resolves policy, retrieves approved policy chunks, verifies safety, and returns a structured recommendation.

Member 2 must add one provider-neutral OpenAI-compatible adapter supporting:

```text
OpenRouter: https://openrouter.ai/api/v1
Groq:       https://api.groq.com/openai/v1
```

Planned environment configuration:

```env
RESOLVEONE_LLM_PROVIDER=groq
RESOLVEONE_LLM_MODEL=<frozen-model-id>
GROQ_API_KEY=<secret>
OPENROUTER_API_KEY=<secret>
RESOLVEONE_LLM_TIMEOUT_SECONDS=30
```

API keys belong only in the ignored `.env` or a deployment secret store. They must never be committed, sent to the browser, included in model prompts, written to receipts, or logged.

The LLM may:

- classify `EXPLAIN`, `QUERY`, and `ACT` intents;
- compose evidence- and policy-grounded explanations;
- return cited answers;
- generate a strictly validated `ProposedAction`;
- produce analyst-facing summaries and safe refusals.

The LLM may never:

- mint or modify an access context;
- grant `ALLOW`, `DENY`, or `REQUIRE_APPROVAL`;
- approve a proposal;
- change tenant, queue, role, or field scope;
- control the kill switch;
- directly execute a retry, refund, reversal, or escalation;
- finalize a governance receipt.

Every model response is untrusted input. Pydantic schema validation, citation validation, policy grounding, restricted-field checks, and prompt-injection checks run before a response becomes a proposal. Provider failure activates the declared deterministic fallback or a safe refusal; it never bypasses governance.

## Governance rules

Neo4j is authoritative for authorization decisions, approvals, receipt revisions, and decision lineage. PostgreSQL/Parquet remains authoritative for operational case facts.

The governed action outcomes are:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

Only `SIMULATE_RETRY_PAYMENT` may execute autonomously during the hackathon. It has no external financial effect. A real `RETRY_PAYMENT` remains human-governed, and no live payment rail is connected.

Examples:

| Scenario | Result |
| --- | --- |
| Technical Glitch, fraud `No`, amount below $250, first simulation | `ALLOW` |
| Fraud `Unknown` or amount at least $250 | `REQUIRE_APPROVAL` by Operations Manager |
| Fraud `Yes` with retry action | `DENY` |
| Retry count at least one | `DENY` |
| Unsupported action | `DENY` |
| Allowed action while autonomy is disabled | No execution; receipt finalized with `AUTONOMY_DISABLED` |

The `FakeGovernanceAdapter` is for isolated development and contract tests only. Production and integrated runtime paths must use Neo4j and fail closed when it is unavailable.

## Repository layout

```text
agent/          Existing deterministic LangGraph agent and policy retrieval
contracts/      Frozen typed contracts shared by all three members
governance/     Member 1 access, authorization, approvals, receipts and UI harness
trust_graph/    Neo4j client, schema, repository and lineage projection
data/           Local raw and processed data products; ignored by Git
policies/       Approved payment-exception policy documents
reports/        Generated evaluation evidence
requirements/   Member-specific dependency files
scripts/        Data, validation and evidence-generation scripts
styles/         Streamlit design system
tests/          Agent, governance, graph, security, evaluation and UI tests
utils/          Existing main-UI adapters and legacy runtime store
app.py          Existing main Streamlit operations UI; Member 3 integration entry point
implementation.md  Complete contracts, ownership, integration and acceptance plan
```

## Prerequisites

- Python 3.12
- Gold Parquet at `data/processed/gold_exception_cases.parquet`
- Neo4j Community or Enterprise for the real Member 1 backend
- PostgreSQL with pgvector for live policy retrieval
- Redis for persistent agent replay protection

PostgreSQL and Redis are optional for viewing the current UI. When pgvector is unavailable, the existing UI labels the response as an approved-policy deterministic fallback and does not claim a live retrieval score.

Neo4j is not optional for the real governance backend. Member 1 never silently falls back to memory.

## Setup on Windows

Create or activate the project environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r agent\requirements.txt
python -m pip install -r requirements\member1.txt
python -m pip install streamlit plotly
```

Create the ignored local environment file:

```powershell
Copy-Item .env.example .env
```

Configure at minimum:

```env
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<local-password>
NEO4J_DATABASE=neo4j
RESOLVEONE_CONTEXT_SIGNING_KEY=<random-secret>
RESOLVEONE_RECEIPT_SIGNING_KEY=<different-random-secret>
RESOLVEONE_GOLD_PARQUET=data/processed/gold_exception_cases.parquet
```

Never commit `.env`. The repository ignores `.env`, local Neo4j runtime data, Streamlit secrets, generated logs, and processed data.

## Running the current applications

### Existing operations UI

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501`.

This is the existing queue, investigation, recommendation, local approval and metrics interface. Its SQLite approval trail is legacy demo persistence and must not remain a second authoritative governance record after Member 3 integration.

### Member 1 governance console

Start Neo4j first, then run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run governance\demo_app.py
```

The console supports:

- trusted demo identities and signed 30-minute access contexts;
- real Parquet case facts and Neo4j retry history;
- deterministic authorization;
- maker-checker approval;
- receipt finalization;
- interactive pan/zoom/hover decision-lineage graph;
- JSON receipt and lineage audit views.

This console is a focused Member 1 test harness, not the final judge entry point.

## Policy RAG configuration

Set the PostgreSQL connection string and build the governed policy index:

```powershell
$env:RESOLVEONE_PG_DSN = "dbname=resolveone user=resolveone password=change-me host=localhost port=5432"
psql -d resolveone -c "CREATE EXTENSION IF NOT EXISTS vector;"
.\.venv\Scripts\python.exe -m agent.build_index
```

Redis defaults to `localhost:6379/0` and can be overridden with:

```env
RESOLVEONE_REDIS_HOST=localhost
RESOLVEONE_REDIS_PORT=6379
RESOLVEONE_REDIS_DB=0
```

## Testing

Run Member 1 unit tests and live Neo4j integration tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\governance tests\trust_graph -q -rs
```

Run the existing agent, evaluation and security suites:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\agent tests\evaluation tests\security -v
```

Run the current UI/data tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ui -q
```

Validate the Gold product:

```powershell
.\.venv\Scripts\python.exe scripts\validate_gold.py
```

Generate Member 1 evidence:

```powershell
.\.venv\Scripts\python.exe scripts\generate_member1_report.py
```

The generated report is written to `reports/member1/governance_results.json`. Integration tests skip with an explicit reason when Neo4j credentials or connectivity are unavailable.

## Evaluation and judge evidence

The final dashboard must read generated artifacts rather than displaying hard-coded claims.

Required evidence includes:

- authorization scenario accuracy and unauthorized bypasses;
- receipt and lineage completeness;
- intent accuracy, action-plan accuracy and citation completeness;
- prompt-injection success and PII leakage rates;
- end-to-end recovery success;
- kill-switch bypass count;
- p50 and p95 latency;
- provider/model, token usage and estimated LLM cost;
- transparent estimates of manual touches and analyst minutes saved.

The final judge story is:

> **Sense → Understand → Govern → Act → Verify → Prove**

## Data and privacy boundary

The application reads only approved governed projections. It must not expose or send raw client identifiers, raw card identifiers, full card numbers, CVV, PIN, address, latitude, longitude, credentials, or signing keys.

Fraud `Unknown` is a first-class state and must never be converted to `No`. Model providers receive only the minimum masked evidence and approved policy content required for the task.

Do not store hidden model chain-of-thought. Store validated answers, structured proposals, citations, reason codes, provider/model metadata, latency, token usage and declared fallback reasons.

## Documentation

- [Complete implementation plan](implementation.md)
- [Member 1 governance runbook](docs/member1/README.md)
- [Agent architecture](docs/AGENT_ARCHITECTURE.md)
- [MDM applied to RAG](docs/MDM_RAG.md)
- [Policy library](docs/POLICY_LIBRARY.md)
- [Agent evaluation](docs/EVALUATION.md)
- [Agent traces](docs/AGENT_TRACES.md)
- [Gold data handoff](docs/README_DATA.MD)
- [Operational runbook](docs/RUNBOOK.md)
- [GCP setup and production guidance](docs/gcp/README.md)
