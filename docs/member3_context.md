Member 3 Integration Context (LLM-ready)
======================================

Purpose
-------
This document provides a compact, authoritative context for Member 3 (integration, orchestration, execution, UI) so an LLM or developer can implement the integration without browsing the whole repository.

High-level workflow (orchestrator)
---------------------------------
1. Receive a synthetic PAYMENT_EXCEPTION_CREATED event.
2. Load the canonical `Case` by exception_id.
3. Call Member 2: `investigate_exception(case)` → `ProposedAction`.
4. Obtain or transport a validated `AccessContext` (minted by Member 1 if needed).
5. Build `AuthorizationRequest` and call Member 1: `authorize_action(request, access_context)` → `AuthorizationResponse`.
6. Persist an initial governance receipt via `create_governance_receipt(...)` (Member 1) if not created by `authorize_action`.
7. Branch on `AuthorizationResponse.decision`: `ALLOW` | `DENY` | `REQUIRE_APPROVAL`.
8. If `ALLOW`: check Member 3 kill switch (persisted state). If enabled and autonomy allowed, call `retry_payment(request)` (sandbox only).
9. Verify any execution result (`verifier`) and call Member 1: `finalize_governance_receipt(receipt_id, execution_result, ...)`.
10. Refresh lineage via Member 1: `get_case_lineage(exception_id)` and update the UI/metrics.

Public APIs to call (contracts & locations)
-----------------------------------------
- Member 2 (investigation/chat)
  - `investigate_exception(case) -> ProposedAction` — [agent_v2/api.py](agent_v2/api.py)
  - `handle_chat(request, access_context) -> ChatResponse` — [chat/api.py](chat/api.py)

- Member 1 (governance)
  - `mint_access_context(session) -> AccessContext` — [governance/api.py](governance/api.py)
  - `validate_access_context(context) -> AccessContext` — [governance/api.py](governance/api.py)
  - `authorize_action(request, access_context) -> AuthorizationResponse` — [governance/api.py](governance/api.py)
  - `create_governance_receipt(...) -> GovernanceReceipt` — [governance/api.py](governance/api.py)
  - `finalize_governance_receipt(receipt_id, execution_result, ...) -> GovernanceReceipt` — [governance/api.py](governance/api.py)
  - `get_case_lineage(exception_id, access_context) -> CaseLineage` — [governance/api.py](governance/api.py)

- Member 3 (execution & orchestrator)
  - `retry_payment(request) -> ExecutionResult` (sandbox only) — [execution/api.py](execution/api.py)
  - Orchestrator entry: [integration/orchestrator.py](integration/orchestrator.py)

Contracts summary (keys only — minimal for quick validation)
---------------------------------------------------------
- Case: `exception_id`, `transaction_id`, `exception_type`, `amount`, `fraud_label`, `risk`, `severity`, `masked_card_id`, `retry_count`, `status`.
- AccessContext: `context_id`, `user_id`, `canonical_role`, `allowed_queues`, `can_view_risk_fields`, `tenant_id`, `issued_at`, `expires_at`, `integrity_hash`.
- ProposedAction: `proposal_id`, `exception_id`, `agent_id`, `action`, `reason_codes`, `explanation`, `policy_id`, `policy_version`, `citations`, `confidence`.
- AuthorizationRequest: `request_id`, `access_context_id`, `agent_id`, `exception_id`, `action`, `policy_id`, `asserted_case_context`.
- AuthorizationResponse: `authorization_id`, `receipt_id`, `decision` (ALLOW/DENY/REQUIRE_APPROVAL), `reason_codes`, `requires_human`, `required_approver_role`, `policy_citations`.
- ExecutionResult: `execution_id`, `trace_id`, `exception_id`, `action`, `status` (SUCCESS/FAILED), `reference`, `verified`, `started_at`, `completed_at`.
- GovernanceReceipt: `receipt_id`, `authorization_id`, `request_id`, `trace_id`, `tenant_id`, `exception_id`, `user_id`, `canonical_role`, `agent_id`, `policy_citations`, `evidence_ids`, `reason_codes`, `action`, `authorization`, `approval_id`, `receipt_state`, `outcome`, `outcome_reason`, `integrity_hash`, `timestamp`.
- Error envelope: `trace_id`, `status`="ERROR", `error_code`, `message`, `retryable`.

Key constraints and rules (enforceable by LLM or code)
---------------------------------------------------
- Never execute real payment rails. Only call `retry_payment` sandbox implementation in `execution/`.
- Do not accept role or identity from UI; derive principal and role from `AccessContext` validated by Member 1.
- `investigate_exception` and LLM proposals must not grant authority — they only return a `ProposedAction`.
- `AuthorizationRequest.access_context_id` must match the validated `AccessContext.context_id`.
- Execution must check the kill-switch state immediately before any call.
- All receipts revisions must be handled by Member 1; Member 3 only requests create/finalize.

Files and fakes to use or replace (Member 3 scope)
------------------------------------------------
- Orchestrator: [integration/orchestrator.py](integration/orchestrator.py)
- Event simulator: [events/producer.py](events/producer.py)
- Orchestrator fakes: [integration/fakes/fake_agent.py](integration/fakes/fake_agent.py), [integration/fakes/fake_governance.py](integration/fakes/fake_governance.py), [integration/fakes/fake_access_context.py](integration/fakes/fake_access_context.py), [integration/fakes/fake_lineage.py](integration/fakes/fake_lineage.py)
- Execution gateway & verifier: [execution/api.py](execution/api.py), [execution/gateway.py](execution/gateway.py), [execution/verifier.py](execution/verifier.py), [execution/kill_switch.py](execution/kill_switch.py)
- UI entry: [app.py](app.py) and [ui_v2/app.py](ui_v2/app.py)
- Telemetry & metrics: [observability/telemetry.py](observability/telemetry.py), [observability/metrics.py](observability/metrics.py)

Run & test commands (quick)
---------------------------
Run unit tests for integration and execution:

```bash
py -m pytest tests/integration/ -q
py -m pytest tests/execution/ -q
```

Run the demo UI (Member 3 owns `app.py`):

```bash
py app.py
# or
streamlit run app.py
```

Environment variables (important)
--------------------------------
- `RESOLVEONE_LLM_PROVIDER`, `RESOLVEONE_LLM_MODEL`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `RESOLVEONE_LLM_TIMEOUT_SECONDS` — Member 2 LLM config (do not embed keys)
- `RESOLVEONE_KILL_SWITCH` — optional environment override for autonomy during demo

Golden fixtures and evaluation inputs (locations)
------------------------------------------------
- Golden case: `tests/fixtures/golden_case_exc101.json` (or `tests/integration/fixtures/` if present)
- Authorization fixtures: `tests/governance/fixtures/*.json`
- Agent proposals: `tests/agent_v2/fixtures/*.json`

Acceptance criteria (minimum for integration branch)
--------------------------------------------------
1. End-to-end Technical Glitch golden scenario runs from event → investigate → authorize → (ALLOW) → sandbox retry → verify → finalize receipt.
2. Kill switch OFF: execution call count = 0, receipt outcome = `NOT_EXECUTED` with `AUTONOMY_DISABLED` reason.
3. REQUIRE_APPROVAL produces pending receipt and no execution until an authorized approval is recorded.
4. DENY produces final receipt with `NOT_EXECUTED` outcome.
5. All public API calls use fakes interchangeably with real adapters (adapter swap must not require business logic changes).

Notes for an LLM implementing Member 3
------------------------------------
- Use the provided fakes in `integration/fakes/` to iterate quickly; ensure signatures match contracts above.
- Keep the orchestration logic pure: call Member 2 for proposals, Member 1 for authorization and receipts, then enforce kill-switch and call local sandbox `retry_payment`.
- Log trace_id on every step and populate telemetry counters for model calls, authorization calls, execution calls, latency, and success/failure.
- Preserve all policy citations, receipt IDs, and evidence references returned by Member 1 and Member 2; include them in the UI and lineage projection.
- Implement thorough defensive checks: validated `AccessContext`, `exception_id` existence, schema validation of `ProposedAction`, and execution verification.

Contact points (quick lookup)
----------------------------
- Member 1 governance code: [governance/](governance/)
- Member 2 agent & chat: [agent_v2/](agent_v2/) and [chat/](chat/)
- Member 3 integration: [integration/](integration/), [events/](events/), [execution/](execution/), [ui_v2/](ui_v2/)

If you want, I can:
- open the orchestrator and add a starter implementation that wires the fakes end-to-end, or
- run the integration tests and report failures to iterate.

Generated: 2026-08-18
