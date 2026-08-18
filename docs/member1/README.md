# Member 1 — Governance and Decision Trust Graph

Member 1 verifies a signed access context, loads a governed Gold case projection,
authorizes deterministically, records maker-checker approval, and persists a
tamper-evident receipt plus scoped lineage in Neo4j.

## Setup

Use the project environment from the repository root:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `NEO4J_PASSWORD`, `RESOLVEONE_CONTEXT_SIGNING_KEY`, and
`RESOLVEONE_RECEIPT_SIGNING_KEY` in the process environment. Neo4j must be a
locally running server; Docker is not required and there is no in-memory fallback.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest tests\governance -q
.venv\Scripts\python.exe -m pytest tests\trust_graph -q
.venv\Scripts\python.exe scripts\generate_member1_report.py
```

Integration tests skip with a stated reason if `NEO4J_PASSWORD` is absent or the
configured server fails `verify_connectivity()`. `governance.fakes.FakeGovernanceAdapter`
is the fixture-backed handoff adapter for Member 2 and Member 3 development only.
