ResolveOne — Member 3 Integration (Run Instructions)
===============================================

Purpose
-------
This file describes how to run the Member 3 integration end-to-end locally using the provided fakes and sandbox execution. It assumes you are in the repository root.

Prerequisites
-------------
- Windows or Unix environment with Python 3.10+ installed.
- Install project dependencies (recommended in a venv).

Install dependencies (minimal)
------------------------------
```bash
py -m venv .venv
.\.venv\Scripts\activate   # Windows
# or on Unix: source .venv/bin/activate
py -m pip install --upgrade pip
py -m pip install streamlit pandas plotly
```

Run the UI (Streamlit)
----------------------
Start the Streamlit app (this loads the Member 3 orchestrator button if present):

```bash
py -m streamlit run app.py
```

Run the Member 3 demo runner (headless)
-------------------------------------
This invokes the orchestrator with a golden case and writes telemetry to `reports/member3/runtime_results.json`.

```bash
py integration/run_demo.py
```

Run integration smoke tests (no pytest required)
----------------------------------------------
```bash
py scripts/run_integration_tests_local.py
```

Toggle kill switch
------------------
Disable autonomous execution:
```bash
py -c "from execution.kill_switch import KillSwitch; ks=KillSwitch(); ks.set_enabled(False)"
```
Re-enable:
```bash
py -c "from execution.kill_switch import KillSwitch; ks=KillSwitch(); ks.set_enabled(True)"
```

Telemetry and reports
---------------------
Workflow results are appended to `reports/member3/runtime_results.json`.

Notes
-----
- All execution is sandbox-only. No external payment rails are contacted.
- The orchestrator uses the fakes in `integration/fakes/` and the governance fake to simulate Member 1 behavior.
- For production integration, replace the fakes with real adapters matching the public API contracts.

Productionization notes
-----------------------
- Use environment variables or a secrets manager to set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and the signing keys. See `member3/config.py` for names.
- The server exposes a health endpoint at `/healthz` and Prometheus metrics at `/metrics` (when `prometheus_client` is installed).
- Install production dependencies with:

```bash
py -m pip install -r requirements/member3.txt
```

- To run the production-ready wrapper locally:

```bash
py member3_server.py
```

Using the real governance API (dev fallback)
-------------------------------------------
- The server can prefer the repository's `governance` service when started with the environment variable `USE_REAL_GOV=1`.
- For local development, the governance service will automatically fall back to a lightweight dev wrapper that delegates to the integration fakes when required environment variables (Neo4j or signing keys) are missing. This allows exercising the "real" code paths without an operational Neo4j instance or secrets.
- To start the server in real-gov preference (dev fallback will be used if necessary):

```powershell
set USE_REAL_GOV=1
py -m uvicorn member3_server:app --host 127.0.0.1 --port 8000
```

- To enable real governance against your Neo4j instance and signing keys, set the following environment variables before starting the server:

```
NEO4J_URI
NEO4J_USER
NEO4J_PASSWORD
NEO4J_DATABASE
RESOLVEONE_CONTEXT_SIGNING_KEY
RESOLVEONE_RECEIPT_SIGNING_KEY
```

- Note: When `USE_REAL_GOV=1` is set but required env vars are omitted, the dev fallback prevents startup-time failures and preserves demo flows; it is not suitable for production use.

Limitations
-----------
- This repository contains demo fakes for Member 1 and Member 2: you must implement or configure adapters to point at real services for full production integration.
- Do not commit secrets into the repo. Use environment variables or an external secrets store for production credentials.
