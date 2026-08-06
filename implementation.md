# ResolveOne AI — Implementation Plan

## 1. Project Summary

**ResolveOne AI** is a governed finance-exception management system for failed payment transactions.

The capstone will demonstrate one complete workflow:

> Detect a failed-payment exception, classify its severity, retrieve the applicable resolution policy, recommend the next best action, route the case to the correct operations team, require human approval where necessary, and retain a complete audit trail.

The capstone must use public or synthetic data and must run live during the evaluation.

---

## 2. Scope

### Capstone MVP

The working capstone will include:

1. Ingestion of transaction, card, merchant-category and optional fraud-label data.
2. Bronze–Silver–Gold data pipelines.
3. Data contracts and automated quality checks.
4. Detection and classification of failed-payment exceptions.
5. Deterministic severity scoring and queue routing.
6. RAG over an approved synthetic resolution-policy library.
7. Evidence-backed next-best-action recommendations.
8. Human approval or rejection for controlled actions.
9. Prompt, tool, evidence and analyst-decision audit trails.
10. A Streamlit operations interface.
11. Evaluation of routing, retrieval, latency, data quality and safety.

### Not part of the capstone MVP

These must be presented only as future capabilities:

- OCR-based document mismatch detection.
- Live bank or payment-gateway integration.
- Autonomous retries, refunds, reversals or account changes.
- Multi-enterprise tenancy.
- Mule-account or customer-network detection.
- Permanent card or account blocking.

---

## 3. Business Context

- **Industry:** Financial Services
- **Business function:** Finance Operations / Payment Operations
- **Primary user:** Finance Exception Operations Analyst
- **Secondary users:** Payment Operations Manager, Fraud Analyst, Reconciliation Analyst, Supervisor, Compliance Reviewer
- **Workflow improved:** Determine the cause, severity, applicable policy, next action and owner of each failed payment.

### Target outcomes

- Faster exception triage.
- More consistent case routing.
- Lower manual investigation effort.
- Policy-grounded recommendations.
- Better auditability.
- Fewer duplicate cases.
- Safer use of AI in finance operations.

---

## 4. Data Sources

### Existing uploaded data

Use the uploaded **Financial Transactions Dataset Analytics** files:

- `transactions_data.csv`
- `cards_data.csv`
- `mcc_codes.json`
- `train_fraud_labels.json`
- `users_data.csv` — optional and restricted

The `errors` field already provides useful exception categories:

- Insufficient Balance
- Bad PIN
- Technical Glitch
- Bad Card Number
- Bad Expiration
- Bad CVV
- Bad Zipcode

### Synthetic supporting data

No new transaction dataset is required. Create only a small synthetic policy library because internal bank procedures are not present in the public data:

```text
policies/
├── insufficient_balance.md
├── bad_pin.md
├── technical_glitch.md
├── bad_card_number.md
├── bad_expiration.md
├── bad_cvv.md
└── bad_zipcode.md
```

Each policy must define:

- Exception definition
- Default severity
- Responsible team
- Evidence required
- Recommended action
- Prohibited action
- Human-approval requirement
- SLA
- Escalation rule

---

## 5. Governed Data Product

### Product name

`finance_exception_case_gold`

### Grain

One record per payment-exception case.

### Suggested Gold schema

```text
exception_id
transaction_id
transaction_timestamp
masked_client_id
masked_card_id
amount
transaction_channel
merchant_category
merchant_state
error_code
error_group
fraud_indicator
severity
recommended_queue
recommended_action
policy_reference
evidence_record_ids
confidence
approval_required
case_status
analyst_decision
analyst_reason
created_at
resolved_at
pipeline_run_id
model_version
policy_version
```

### Contract requirements

- `exception_id` must be unique and non-null.
- `transaction_id` must be non-null.
- `error_code` must belong to the approved domain.
- `severity` must be `LOW`, `MEDIUM`, `HIGH` or `CRITICAL`.
- `recommended_queue` must belong to the approved queue domain.
- Every recommendation must reference a valid policy.
- Evidence IDs cannot be empty.
- Full card number and CVV must never appear in Gold.
- Every decision must record model and policy versions.
- Controlled actions must record approval status.

---

## 6. Medallion Architecture

```text
Public / Synthetic Source Files
            ↓
Bronze — immutable source-aligned tables
            ↓
Silver — validated, standardized and masked entities
            ↓
Gold — governed finance exception cases
            ↓
Rules + RAG + LangGraph agent
            ↓
Human approval
            ↓
Case routing and audit history
```

### Bronze tables

- `bronze_transactions`
- `bronze_cards`
- `bronze_mcc_codes`
- `bronze_fraud_labels`
- `bronze_users_restricted`

Capture ingestion timestamp, filename, file checksum, row number, row hash and pipeline run ID.

### Silver tables

- `silver_transactions`
- `silver_cards_masked`
- `silver_merchant_category`
- `silver_transaction_fraud_context`
- `silver_payment_exceptions`
- `silver_resolution_policy`

Silver processing includes timestamp parsing, amount standardization, error normalization, ID tokenization, sensitive-column removal, MCC mapping and data-quality status.

### Gold and supporting tables

- `finance_exception_case_gold`
- `golden_payment_profile`
- `exception_decision_audit`
- `agent_tool_trace`
- `analyst_approval_history`
- `pipeline_quality_summary`

---

## 7. Master Data Management

### Golden entity

`golden_payment_profile`

One record per masked `card_id`, including:

- Masked card and client IDs
- Card brand and type
- Chip support
- Credit limit
- Dark-web indicator
- Historical transaction count
- Historical exception count and rate
- Latest activity date
- Source-of-record metadata

### Survivorship rules

- `cards_data.csv` is authoritative for card attributes.
- `transactions_data.csv` is authoritative for transaction behavior.
- `train_fraud_labels.json` is authoritative only for labelled transactions.
- The most recent valid operational record wins where duplicates exist.
- Restricted fields never propagate into the agent-facing Gold layer.

---

## 8. Exception Classification and Routing

| Exception | Default severity | Queue | Suggested action |
|---|---|---|---|
| Insufficient Balance | Low | Customer Payment Support | Request alternate payment or notify |
| Bad PIN | Medium | Card Support | Step-up verification or controlled retry |
| Technical Glitch | High | Payment Operations | Confirm service status and controlled retry |
| Bad Card Number | Medium | Payment Validation | Correct payment details |
| Bad Expiration | Medium | Card Support | Update card details |
| Bad CVV | High | Card Security Review | Verification before retry |
| Bad Zipcode | Low | Payment Validation | Correct billing details |

Severity may increase when the amount is high, exceptions repeat, fraud context is present, retries fail or an SLA deadline is near.

For the MVP, severity and routing should be deterministic and explainable. The LLM explains the outcome; it does not invent or override the rule.

---

## 9. Agentic Workflow

### LangGraph flow

```text
Receive exception
      ↓
Validate contract
      ↓
Fetch governed evidence
      ↓
Calculate severity and queue
      ↓
Retrieve the relevant resolution policy
      ↓
Generate an evidence-backed explanation
      ↓
Run policy and safety verification
      ↓
Require human approval where needed
      ↓
Record the decision and route the case
```

### Controlled tools

```text
get_exception_case(exception_id)
get_transaction_evidence(transaction_id)
get_payment_profile(masked_card_id)
retrieve_resolution_policy(error_code)
calculate_exception_severity(exception_id)
calculate_recommended_queue(exception_id)
create_resolution_recommendation(exception_id)
submit_for_human_approval(exception_id)
record_analyst_decision(exception_id)
```

### Trust boundary

The LLM may summarize governed evidence, explain a policy and produce a structured recommendation.

It may not:

- Modify balances.
- Retry, reverse or refund a payment.
- Block a card or account.
- Access full card number, CVV or unrestricted personal data.
- Bypass approval.
- Invent missing evidence.
- Execute arbitrary SQL.

---

## 10. Retrieval-Augmented Generation

Use PostgreSQL with `pgvector` as the preferred vector store. Use one vector database only.

Every retrieval result must include:

- Policy ID
- Policy title
- Exception type
- Policy version
- Relevant section
- Similarity score
- Source citation

Evaluate:

- Top-1 retrieval accuracy
- Top-3 retrieval accuracy
- Citation completeness
- Groundedness
- Unsupported recommendation rate

---

## 11. Security and Governance

### Classification examples

| Field | Classification |
|---|---|
| transaction_id | Identifier |
| client_id | Restricted identifier |
| card_id | Restricted identifier |
| card_number | Highly sensitive |
| CVV | Prohibited from agent access |
| amount | Financial |
| error_code | Operational |
| fraud_label | Restricted risk signal |
| user address | PII |

### Controls

- Tokenize customer and card identifiers.
- Exclude full card number and CVV from agent views.
- Keep user data in a restricted schema.
- Store secrets outside source code.
- Use read-only agent tools.
- Version policies and models.
- Require approval for high-risk actions.
- Log prompts, tools, outputs and approvals.
- Fail closed when contract or policy verification fails.

### Prompt-injection defence

- Treat business data as evidence, never as instructions.
- Validate category fields against approved domains.
- Isolate untrusted text.
- Pass typed tool responses instead of raw unrestricted rows.
- Use an independent policy verifier.
- Block unauthorized tool calls.
- Record attempted security violations.

---

## 12. Technology Stack

### Capstone sandbox lane

**VM-only**

### Core stack

- Python 3.12
- PySpark
- Delta Lake
- dbt
- Apache Airflow
- PostgreSQL
- pgvector
- LangGraph
- Redis
- Streamlit
- FastAPI or Flask
- Prometheus
- Grafana
- Docker Compose
- GitHub

### Excluded from MVP unless needed

- CrewAI
- AutoGen
- Neo4j
- Flink
- Multiple vector databases
- Multi-cloud deployment

---

## 13. Repository Structure

```text
resolveone-ai/
├── README.md
├── implementation.md
├── docker-compose.yml
├── .env.example
├── data/
│   ├── raw/
│   ├── samples/
│   └── processed/
├── contracts/
│   └── finance_exception_contract.yml
├── dbt/
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   └── tests/
├── dags/
│   └── exception_pipeline.py
├── src/
│   ├── ingestion/
│   ├── transformations/
│   ├── quality/
│   ├── mdm/
│   └── governance/
├── agent/
│   ├── graph.py
│   ├── state.py
│   ├── tools.py
│   ├── policy_gate.py
│   ├── prompts.py
│   └── evaluation.py
├── policies/
├── app/
│   ├── streamlit_app.py
│   └── api.py
├── monitoring/
│   ├── prometheus.yml
│   └── dashboards/
├── tests/
│   ├── data/
│   ├── pipeline/
│   ├── agent/
│   ├── security/
│   └── evaluation/
└── Persistent_Folder/
    └── resolveone-ai/
```

---

## 14. Implementation Phases

### Phase 1 — Foundation and profiling

Tasks:

- Create the GitHub repository and add collaborators.
- Add `.gitignore`, `.env.example` and branch rules.
- Declare the VM-only sandbox lane.
- Profile all source files.
- Create a manageable development sample.
- Document public/synthetic data status.
- Define the product owner, consumers, SLA and limitations.
- Create the first architecture diagram and YAML contract.

Proof:

- Dataset profile
- Data-product specification
- Architecture diagram
- Data contract
- Source inventory
- Training-data-only statement

### Phase 2 — Bronze–Silver–Gold pipeline

Tasks:

- Load source files into Bronze.
- Create Silver models.
- Create `finance_exception_case_gold`.
- Add dbt tests.
- Add Airflow orchestration.
- Add rejection and pipeline-run logs.

Proof:

- Successful pipeline run
- Failed-contract example
- dbt test report
- Gold preview

### Phase 3 — Governance, lineage and MDM

Tasks:

- Mask and tokenize identifiers.
- Build `golden_payment_profile`.
- Create classification metadata.
- Build source-to-Gold lineage.
- Implement role- and purpose-based access decisions.

Proof:

- Classification report
- MDM result
- Survivorship rules
- Lineage evidence
- Access-control decisions

### Phase 4 — Policy RAG

Tasks:

- Create seven policy documents.
- Add policy IDs and versions.
- Generate embeddings.
- Store vectors in pgvector.
- Implement citation-aware retrieval.
- Create retrieval tests.

Proof:

- Policy library
- Vector index
- Retrieval tool
- Retrieval evaluation report

### Phase 5 — LangGraph agent

Tasks:

- Define the state schema.
- Implement controlled tools.
- Add deterministic severity and routing.
- Add the recommendation node.
- Add the policy-verifier node.
- Add a human-approval checkpoint.
- Add Redis idempotency.
- Persist tool and decision traces.

Proof:

- Agent graph
- Tool contracts
- Approval workflow
- Agent trace
- Replay/idempotency result

### Phase 6 — User interface

Build four screens:

1. Exception Queue
2. Case Investigation
3. Recommendation and Approval
4. Audit and Metrics

The user must be able to complete the demo without opening a notebook.

### Phase 7 — Monitoring and reliability

Tasks:

- Add `/health` and `/ready` endpoints.
- Add smoke tests.
- Track pipeline failures, API latency, agent latency and retrieval errors.
- Add Prometheus and Grafana.
- Add Docker Compose.
- Prepare fallback screenshots or a recorded run.

### Phase 8 — Evaluation and proof pack

Capture data, agent, security and business metrics. Store all evidence in the required proof folder.

---

## 15. Evaluation Metrics

### Data and pipeline

- Contract pass/fail rate
- Data-quality test pass rate
- Invalid-record count
- Duplicate-case count
- Join coverage
- Pipeline duration
- Gold freshness

### Agent and RAG

- Exception detection accuracy
- Routing accuracy
- Policy top-1 retrieval accuracy
- Citation completeness
- Recommendation groundedness
- Unsupported recommendation rate
- Recommendation latency
- Human override rate

### Security

- Sensitive-field leakage count
- Unauthorized tool-call count
- Approval-bypass count
- Duplicate case creation during replay
- Prompt-injection success rate

### Business

- Manual triage time
- Assisted triage time
- Estimated time saved per case
- Estimated operational cost per case
- SLA-risk cases detected
- Resolution consistency

### Initial targets

These are targets to test, not claims:

| Metric | Target |
|---|---:|
| Demo pipeline test pass rate | 100% |
| Known exception detection | 100% |
| Routing accuracy | At least 90% |
| Policy top-1 retrieval accuracy | At least 90% |
| Citation completeness | 100% |
| Sensitive-data leakage | 0 |
| Unauthorized actions executed | 0 |
| Duplicate cases after replay | 0 |
| Approval bypass | 0 |

---

## 16. Live Demo Path

1. Start local services.
2. Run the pipeline.
3. Show contract and quality-test results.
4. Open the Streamlit exception queue.
5. Select a `Technical Glitch` exception.
6. Show masked evidence and lineage.
7. Run the LangGraph investigation.
8. Show the retrieved policy and citation.
9. Show severity, queue, reason codes and next action.
10. Approve or reject the recommendation.
11. Show the complete audit trace.
12. Replay the event and prove no duplicate case is created.
13. Request a prohibited sensitive field and show the request being blocked.
14. Open the metrics dashboard.

---

## 17. Presentation Alignment

### Slide 1 — Title and Team

ResolveOne AI, team name and members.

### Slide 2 — Problem and Business Context

Manual payment-exception handling, affected users and baseline triage process.

### Slide 3 — Solution Overview

Governed data product, policy-grounded recommendation, routing, human approval and audit.

### Slide 4 — Architecture and Tech Stack

Bronze–Silver–Gold, Airflow, dbt, LangGraph, pgvector, Redis, Streamlit and monitoring.

### Slide 5 — Solution in Action

Real screenshots from the working build.

### Slide 6 — Outputs and Evidence

Pipeline tests, routing results, retrieval metrics, security tests and audit trace.

### Slide 7 — Business Value and Scale-Up Path

Measured prototype value, assumptions, hackathon capabilities and production translation.

### Slide 8 — Thank You

Closing statement and repository reference.

---

## 18. Hackathon Scale-Up Path

The capstone proves the core failed-payment exception workflow. The hackathon version expands ResolveOne into an enterprise exception command centre.

### Real-time Kafka processing

- Stream payment failures.
- Track freshness and lag.
- Support replay and dead-letter queues.
- Preserve idempotency.
- Add SLA countdowns.

### OCR document-mismatch agent

- Parse invoices and payment documents.
- Compare extracted values with transaction records.
- Detect amount, date, account and reference mismatches.
- Route cases with cited evidence.

### Multi-agent orchestration

Potential agents:

- Intake Agent
- Triage Agent
- Root-Cause Agent
- Policy Retrieval Agent
- Routing Agent
- Risk Verifier
- Human Approval Agent

### Incident memory

- Store analyst-approved resolutions.
- Retrieve similar past cases.
- Reuse evidence and approved patterns.
- Prevent unsupported autonomous learning.

### SLA and resolution prediction

- Predict resolution time.
- Identify likely SLA breaches.
- Estimate operational and customer impact.
- Prioritize cases dynamically.

### Enterprise integrations

- Payment gateways
- Reconciliation systems
- ServiceNow
- Jira
- CRM platforms
- Notification systems
- Identity and approval services

### Production governance

- Role-based access control
- Secrets manager
- Model and prompt monitoring
- Active metadata
- Policy-as-code
- FinOps
- Cloud deployment
- Regional data controls
- Release approval gates

### Azure production translation

```text
VM storage                    → Azure Data Lake Storage
Local Delta Lake              → Azure Databricks
Local PostgreSQL + pgvector   → Azure Database for PostgreSQL
Local model endpoint          → Azure OpenAI
Airflow                       → Databricks Workflows / Managed Airflow
Prometheus + Grafana          → Azure Monitor
Local secrets                 → Azure Key Vault
Streamlit                     → Azure App Service / Container Apps
```

---

## 19. Proof Folder

Store evidence in:

```text
Persistent_Folder/resolveone-ai/
```

Suggested structure:

```text
Persistent_Folder/resolveone-ai/
├── architecture/
├── contracts/
├── pipeline-runs/
├── quality/
├── lineage/
├── mdm/
├── access-control/
├── agent-traces/
├── evaluation/
├── monitoring/
├── roi/
├── screenshots/
├── fallback-demo/
├── limitations/
└── cleanup/
```

Required proof includes:

- Sandbox lane declaration
- Architecture diagram
- Data contract
- Pipeline run evidence
- Quality results
- Lineage and classification evidence
- MDM evidence
- Access-control decision
- Agent prompt/tool/action trace
- Evaluation report
- Cost and ROI estimate
- Known limitations
- Live demo path
- Backup screenshots or recording
- Public/synthetic-data statement
- Cleanup proof where applicable

---

## 20. Suggested Team Split

### Member 1 — Data Engineering

Ingestion, Bronze–Silver–Gold, dbt, Airflow and quality.

### Member 2 — Governance and MDM

Contract, classification, masking, MDM, lineage and access control.

### Member 3 — Agent and RAG

Policy library, pgvector, LangGraph, tools, approval gate and evaluation.

### Member 4 — Application and Platform

Streamlit, API, Redis, Docker, monitoring and demo integration.

Every member must understand the full solution for Q&A.

---

## 21. Immediate Starting Point

Build one vertical slice first:

```text
Technical Glitch transaction
        ↓
Bronze ingestion
        ↓
Silver validation and masking
        ↓
Gold exception case
        ↓
Technical Glitch policy retrieval
        ↓
Payment Operations recommendation
        ↓
Human approval
        ↓
Audit record
```

Add other exception types only after this path works end to end.

---

## 22. Definition of Done

ResolveOne AI is ready for presentation when:

- The repository is current and accessible.
- The transaction-to-resolution demo runs end to end.
- Pipeline and quality tests pass.
- The Gold product is reproducible.
- Sensitive fields are blocked.
- The correct policy is retrieved and cited.
- The recommendation is evidence-backed.
- Human approval is enforced.
- The audit trace is visible.
- Metrics are measured instead of invented.
- The presentation fits within 15 minutes.
- Backup screenshots or a recording are available.
- Future hackathon capabilities are clearly separated from working capstone functionality.
