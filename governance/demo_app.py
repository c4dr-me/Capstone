"""Interactive Member 1 governance test console."""

from datetime import datetime, timezone
from pathlib import Path
import os
import secrets
import sys

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_local_env() -> None:
    """Load the ignored project .env without adding a runtime dependency."""
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

from contracts import (  # noqa: E402
    AccessContext,
    Action,
    ApprovalDecision,
    AuthenticatedSession,
    AuthorizationRequest,
    ExecutionResult,
)
from contracts.errors import GovernanceError  # noqa: E402
from governance.access_context import AccessContextService  # noqa: E402
from governance.api import GovernanceService  # noqa: E402
from governance.cases import ParquetCaseRepository  # noqa: E402
from governance.fakes import FakeGovernanceAdapter, default_fake_cases  # noqa: E402
from governance.lineage_viz import build_lineage_figure  # noqa: E402
from governance.receipts import ReceiptFactory  # noqa: E402
from governance.settings import GovernanceSettings  # noqa: E402
from trust_graph.neo4j_client import Neo4jClient  # noqa: E402
from trust_graph.repository import Neo4jGovernanceRepository  # noqa: E402
from trust_graph.schema import ensure_schema  # noqa: E402


st.set_page_config(page_title="ResolveOne Governance Console", page_icon="🛡️", layout="wide")


REAL_CASE_IDS = [
    "EXC-8359211",   # low-value Technical Glitch, fraud No
    "EXC-21617011",  # low-value Technical Glitch, fraud Unknown
    "EXC-13981456",  # high-value Technical Glitch, fraud No
    "EXC-8665176",   # Technical Glitch, fraud Yes
]


@st.cache_resource
def runtime():
    backend = os.environ.get("RESOLVEONE_GOVERNANCE_BACKEND", "neo4j").lower()
    if backend == "fake":
        fake = FakeGovernanceAdapter()
        return fake, {case.exception_id: case for case in default_fake_cases()}, None
    if backend != "neo4j":
        raise RuntimeError(f"Unsupported governance backend: {backend}")

    settings = GovernanceSettings.from_env()
    client = Neo4jClient(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        settings.neo4j_database,
    )
    client.verify_connectivity()
    ensure_schema(client)
    repository = Neo4jGovernanceRepository(client)
    case_repository = ParquetCaseRepository(settings.gold_parquet_path, repository)
    service = GovernanceService(
        repository=repository,
        case_repository=case_repository,
        access_contexts=AccessContextService(settings.context_signing_key),
        receipts=ReceiptFactory(settings.receipt_signing_key),
        receipt_signing_key=settings.receipt_signing_key,
    )
    cases = {case_id: case_repository.get_case(case_id) for case_id in REAL_CASE_IDS}
    return service, cases, client


try:
    ADAPTER, CASES, NEO4J_CLIENT = runtime()
except Exception as exc:
    st.error("The governance backend could not be started.")
    st.exception(exc)
    st.stop()


def show_error(error: Exception) -> None:
    if isinstance(error, GovernanceError):
        st.error(f"{error.error_code}: {error}")
    else:
        st.exception(error)


def current_context() -> AccessContext | None:
    payload = st.session_state.get("access_context")
    return AccessContext.model_validate(payload) if payload else None


st.title("ResolveOne — Member 1 Governance Console")
backend = os.environ.get("RESOLVEONE_GOVERNANCE_BACKEND", "fake").lower()
if backend == "neo4j":
    st.success("Live backend: Neo4j. Decisions, approvals, receipt revisions, and lineage persist in the trust graph.")
else:
    st.warning(
        "Development mode: FakeGovernanceAdapter. Decisions use the real Member 1 logic, "
        "but persistence is in-memory—not Neo4j."
    )

st.subheader("1. Trusted identity")
principal = st.selectbox(
    "Principal",
    ["ops_01", "risk_01", "manager_01", "auditor_01", "resolveone_agent"],
)
if st.button("Mint signed 30-minute access context", type="primary"):
    try:
        context = ADAPTER.mint_access_context(AuthenticatedSession(user_id=principal))
        st.session_state.access_context = context.model_dump(mode="json")
        st.session_state.pop("authorization_response", None)
        st.success(f"Minted {context.context_id}")
    except Exception as exc:
        show_error(exc)

context = current_context()
if context:
    st.json(context.model_dump(mode="json"), expanded=False)
else:
    st.info("Mint an access context before authorizing an action.")

st.subheader("2. Deterministic authorization")
left, right = st.columns(2)
with left:
    exception_id = st.selectbox("Case", list(CASES))
with right:
    action = st.selectbox("Requested action", [item.value for item in Action])

case = CASES[exception_id]
st.caption(
    f"{case.exception_type} · ${case.amount:,.2f} · fraud={case.fraud_label} · "
    f"retry_count={case.retry_count} · queue={case.queue}"
)

if st.button("Authorize action", disabled=context is None, type="primary"):
    try:
        assert context is not None
        request_id = f"REQ-UI-{secrets.token_hex(5).upper()}"
        request = AuthorizationRequest(
            request_id=request_id,
            access_context_id=context.context_id,
            agent_id="recovery_agent",
            exception_id=case.exception_id,
            action=action,
            policy_id="POL-TECH-001",
            asserted_case_context={
                "exception_type": case.exception_type,
                "amount": case.amount,
                "fraud_label": case.fraud_label,
            },
            trace_id=request_id.replace("REQ-", "TRACE-", 1),
        )
        response = ADAPTER.authorize_action(request, context)
        st.session_state.authorization_response = response.model_dump(mode="json")
        st.session_state.authorization_case_id = case.exception_id
        st.success(f"Decision: {response.decision}")
    except Exception as exc:
        show_error(exc)

response = st.session_state.get("authorization_response")
if response:
    st.json(response, expanded=True)

    st.subheader("3. Maker-checker approval")
    approver_id = st.selectbox(
        "Approver identity",
        ["manager_01", "ops_01", "risk_01", "auditor_01", "resolveone_agent"],
    )
    approval_decision = st.radio("Approval decision", ["APPROVE", "REJECT"], horizontal=True)
    if st.button("Record approval", disabled=response["decision"] != "REQUIRE_APPROVAL"):
        try:
            approver_context = ADAPTER.mint_access_context(
                AuthenticatedSession(user_id=approver_id)
            )
            decision = ApprovalDecision(
                approval_id=f"APR-UI-{secrets.token_hex(5).upper()}",
                authorization_id=response["authorization_id"],
                access_context_id=approver_context.context_id,
                decision=approval_decision,
                comment="Reviewed in the Member 1 governance console",
            )
            ADAPTER.record_approval(decision, approver_context)
            st.success(f"Approval recorded from trusted identity {approver_id}")
        except Exception as exc:
            show_error(exc)

    st.subheader("4. Execution outcome or kill-switch stop")
    terminal = st.selectbox("Terminal result", ["SUCCESS", "FAILED", "AUTONOMY_DISABLED"])
    if st.button("Finalize receipt"):
        try:
            assert context is not None
            receipt = ADAPTER.get_governance_receipt(response["receipt_id"], context)
            service_context = ADAPTER.mint_access_context(
                AuthenticatedSession(user_id="resolveone_agent")
            )
            if terminal == "AUTONOMY_DISABLED":
                result = None
                reason = terminal
            else:
                now = datetime.now(timezone.utc)
                result = ExecutionResult(
                    execution_id=f"EXEC-UI-{secrets.token_hex(5).upper()}",
                    trace_id=receipt.trace_id,
                    exception_id=receipt.exception_id,
                    action=receipt.action,
                    status=terminal,
                    reference=f"SIM-UI-{secrets.token_hex(4).upper()}",
                    verified=True,
                    started_at=now,
                    completed_at=now,
                )
                reason = None
            final = ADAPTER.finalize_governance_receipt(
                response["receipt_id"], result, reason, service_context
            )
            st.success(f"Receipt finalized: {final.outcome}")
        except Exception as exc:
            show_error(exc)

    st.subheader("5. Receipt and scoped lineage")
    if st.button("Refresh governance proof", disabled=context is None):
        try:
            assert context is not None
            receipt = ADAPTER.get_governance_receipt(response["receipt_id"], context)
            lineage = ADAPTER.get_case_lineage(
                st.session_state.authorization_case_id, context
            )
            st.session_state.receipt_projection = receipt.model_dump(mode="json")
            st.session_state.lineage_projection = lineage.model_dump(mode="json")
        except Exception as exc:
            show_error(exc)

    if st.session_state.get("receipt_projection"):
        lineage_projection = st.session_state.lineage_projection
        proof_metrics = st.columns(4)
        proof_metrics[0].metric("Lineage completeness", f"{lineage_projection['completeness']:.0%}")
        proof_metrics[1].metric("Projected nodes", len(lineage_projection["nodes"]))
        proof_metrics[2].metric("Relationships", len(lineage_projection["edges"]))
        proof_metrics[3].metric(
            "Receipt state", st.session_state.receipt_projection["receipt_state"]
        )
        st.plotly_chart(
            build_lineage_figure(lineage_projection),
            width="stretch",
            config={"displaylogo": False, "scrollZoom": True, "responsive": True},
        )
        receipt_tab, lineage_tab = st.tabs(["Receipt JSON", "Lineage JSON"])
        with receipt_tab:
            st.json(st.session_state.receipt_projection, expanded=False)
        with lineage_tab:
            st.json(lineage_projection, expanded=False)
