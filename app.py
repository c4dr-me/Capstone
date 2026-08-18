"""ResolveOne operations interface backed by the governed Gold data product."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path
from typing import Any


def _load_local_env() -> None:
    """Load developer .env settings before agent and governance imports."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
try:
    import networkx as nx
except Exception:
    nx = None

from utils.agent_adapter import run_investigation
from utils.data_loader import (
    DEFAULT_GOLD_PATH,
    display_exception_type,
    get_case,
    load_gold_data,
    load_quality_results,
    reason_codes_for_case,
    search_cases,
)
from utils.runtime_store import RuntimeStore

# Optional integration orchestrator (Member 3)
try:
    from integration.orchestrator import process_event as integration_process_event, resume_pending_approval as integration_resume_pending_approval
except Exception:
    integration_process_event = None
    integration_resume_pending_approval = None


# Read/remember optional remote endpoints for Member 2 (chat) and Member 3 (orchestrator)
if "member2_url" not in st.session_state:
    st.session_state.member2_url = None
if "member3_url" not in st.session_state:
    st.session_state.member3_url = None


def _call_member2_http(url: str, text: str, exception_id: str | None, access_context: dict | None) -> dict:
    payload = {"text": text}
    if exception_id:
        payload["exception_id"] = exception_id
    if access_context:
        payload["access_context"] = access_context
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _call_member3_http(url: str, event: dict) -> dict:
    resp = requests.post(url, json=event, timeout=20)
    resp.raise_for_status()
    return resp.json()


st.set_page_config(
    page_title="ResolveOne | Exception Operations",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="auto",
)


def _load_css() -> None:
    css_path = Path(__file__).resolve().parent / "styles" / "style.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _get_data() -> pd.DataFrame:
    return load_gold_data()


@st.cache_data(show_spinner=False)
def _get_quality_results() -> dict[str, Any]:
    return load_quality_results()


@st.cache_resource
def _get_runtime_store() -> RuntimeStore:
    return RuntimeStore()


def _format_value(value: Any, fallback: str = "—") -> str:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return fallback
    return str(value)


def _money(value: Any) -> str:
    return "—" if pd.isna(value) else f"${float(value):,.2f}"


def _page_header(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <section class="command-header">
            <div class="command-kicker">{escape(kicker)}</div>
            <h1>{escape(title)}</h1>
            <p>{escape(description)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="signal signal-{tone}">{escape(text)}</span>'


def _severity_tone(severity: str) -> str:
    return {
        "CRITICAL": "critical",
        "HIGH": "high",
        "MEDIUM": "medium",
        "LOW": "low",
    }.get(severity, "neutral")


def _navigate(page_name: str, exception_id: str | None = None) -> None:
    if exception_id:
        st.session_state.selected_exception_id = exception_id
    st.session_state.workspace_page = page_name


def _run_selected_investigation(exception_id: str, status_slot: Any | None = None) -> dict[str, Any]:
    next_step_labels = {
        "validate_contract": "Loading permitted evidence…",
        "fetch_evidence": "Calculating severity and route…",
        "score_severity_and_queue": "Retrieving approved policy…",
        "retrieve_policy": "Building cited recommendation…",
        "generate_recommendation": "Checking policy safeguards…",
        "verify_policy_and_safety": "Preparing human approval checkpoint…",
        "require_human_approval": "Recording governed audit trail…",
        "record_and_route": "Finalizing investigation…",
        "approved_policy_fallback": "Applying approved local-policy fallback…",
    }
    completed_steps: list[str] = []

    def render_progress(label: str) -> None:
        if status_slot is not None:
            status_slot.markdown(
                f'<div class="agent-run-progress"><span class="agent-run-spinner"></span><span>{label}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info(label)

    render_progress("Validating governed case…")

    def on_step(node_name: str) -> None:
        completed_steps.append(node_name)
        render_progress(next_step_labels.get(node_name, "Processing governed workflow…"))

    try:
        result = run_investigation(exception_id, on_step=on_step)
    except Exception:
        if status_slot is not None:
            status_slot.error("ResolveOne could not complete the investigation.")
        raise

    result["workflow_steps"] = completed_steps
    st.session_state.investigation_results[exception_id] = result
    st.session_state.last_agent_mode = result.get("source_mode", "unknown")
    return result

def _chat_display(payload: dict[str, Any]) -> tuple[str, list[str], str | None]:
    """Convert a governed chat response into safe, readable UI content."""
    response = payload.get("response", payload)
    if "error" in response:
        return "The chat service could not process that message.", [], str(response["error"])
    if response.get("source_mode") == "safe_refusal":
        return str(response.get("message", "That request cannot be completed safely.")), [], str(response.get("reason_code", "SAFE_REFUSAL"))
    if response.get("explanation"):
        return str(response["explanation"]), list(response.get("citations", [])), None
    if response.get("explanation") is None and response.get("message"):
        return str(response["message"]), [], None
    if response.get("action"):
        message = f"Proposed action: {response['action']}. {response.get('explanation', '')}".strip()
        return message, list(response.get("citations", [])), None
    if "count" in response:
        return f"Found {response['count']} governed case(s) in your access scope.", [], None
    return "ResolveOne returned an unsupported response format.", [], "UNSUPPORTED_RESPONSE"


def _render_chat_history(messages: list[dict[str, Any]]) -> None:
    for message in messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("citations"):
                st.caption("Policy citations: " + " · ".join(message["citations"]))
            if message.get("notice"):
                st.caption(message["notice"])


def _workflow_role_participants(recovery: dict[str, Any], requester_user_id: str) -> list[dict[str, str]]:
    """Build a truthful role view from the actual recovery result and trusted registry."""
    from governance.roles import IDENTITIES

    proposal = recovery.get("proposal") or {}
    authorization = recovery.get("authorization") or {}
    receipt = recovery.get("receipt") or {}
    approval = recovery.get("approval") or {}
    decision = str(authorization.get("decision", ""))
    outcome = str(recovery.get("status", ""))
    recommended_queue = str(proposal.get("recommended_queue", ""))
    action = str(proposal.get("recommended_action", "a bounded action"))

    def participant(user_id: str, state: str, detail: str) -> dict[str, str]:
        identity = IDENTITIES[user_id]
        return {
            "user_id": identity.user_id,
            "role": str(identity.canonical_role).replace("_", " ").title(),
            "state": state,
            "detail": detail,
        }

    manager_state = "Not required"
    manager_detail = "Policy allowed the workflow to continue without a manager checkpoint."
    if decision == "REQUIRE_APPROVAL":
        approval_decision = str(approval.get("decision", ""))
        if approval_decision:
            manager_state = approval_decision.title()
            manager_detail = "Recorded the required approval decision for this receipt."
        else:
            manager_state = "Awaiting decision"
            manager_detail = "Policy paused this recovery before governed execution."

    risk_route = "RISK" in recommended_queue.upper() or "FRAUD" in recommended_queue.upper()
    risk_state = "In scope" if risk_route else "Not invoked"
    risk_detail = (
        f"The route is {recommended_queue}; risk review can be required by policy."
        if risk_route
        else "This route did not require a risk-review handoff."
    )
    auditor_state = "Audit-ready" if receipt else "Not created"
    auditor_detail = (
        "A governance receipt exists; the decision lineage is available for read-only review."
        if receipt
        else "A receipt will make this workflow available for read-only audit review."
    )

    return [
        participant(requester_user_id, "Completed", "Opened the case and requested governed recovery."),
        participant("resolveone_agent", "Completed", f"Investigated evidence and proposed {action}"),
        participant("manager_01", manager_state, manager_detail),
        participant("risk_01", risk_state, risk_detail),
        participant("auditor_01", auditor_state, auditor_detail),
    ]


def _render_workflow_role_panel(recovery: dict[str, Any], requester_user_id: str) -> None:
    """Render a compact, state-driven Plotly view of governance participation."""
    participants = _workflow_role_participants(recovery, requester_user_id)
    by_user = {item["user_id"]: item for item in participants}
    positions = {
        requester_user_id: (0.0, 0.0),
        "resolveone_agent": (1.0, 0.0),
        "manager_01": (2.0, 0.48),
        "risk_01": (2.0, -0.48),
        "auditor_01": (3.0, 0.0),
    }
    active_manager = by_user["manager_01"]["state"] != "Not required"
    active_risk = by_user["risk_01"]["state"] == "In scope"
    audit_ready = by_user["auditor_01"]["state"] == "Audit-ready"
    links = [(requester_user_id, "resolveone_agent")]
    if active_manager:
        links.append(("resolveone_agent", "manager_01"))
    if active_risk:
        links.append(("resolveone_agent", "risk_01"))
    if audit_ready:
        if active_manager:
            links.append(("manager_01", "auditor_01"))
        if active_risk:
            links.append(("risk_01", "auditor_01"))
        if not active_manager and not active_risk:
            links.append(("resolveone_agent", "auditor_01"))

    state_colors = {
        "Completed": "#167d8d",
        "Approved": "#2f855a",
        "Rejected": "#9b2c2c",
        "Awaiting decision": "#d4a72c",
        "In scope": "#6a5a8c",
        "Audit-ready": "#365b6d",
        "Not required": "#b5b9b6",
        "Not invoked": "#b5b9b6",
        "Not created": "#b5b9b6",
    }
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for source, target in links:
        edge_x.extend([positions[source][0], positions[target][0], None])
        edge_y.extend([positions[source][1], positions[target][1], None])

    node_x, node_y, node_text, node_hover, node_color, node_size = [], [], [], [], [], []
    for user_id, participant in by_user.items():
        x, y = positions[user_id]
        state = participant["state"]
        muted = state in {"Not required", "Not invoked", "Not created"}
        node_x.append(x)
        node_y.append(y)
        node_text.append(f"{participant['role']}<br><sup>{state}</sup>")
        node_hover.append(
            f"<b>{participant['role']}</b><br>User: {participant['user_id']}"
            f"<br>Status: {state}<br>{participant['detail']}"
        )
        node_color.append(state_colors.get(state, "#6b7280"))
        node_size.append(24 if muted else 34)

    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines", hoverinfo="skip", showlegend=False,
        line={"color": "#7c9198", "width": 2.2},
    ))
    figure.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text", text=node_text,
        textposition="bottom center", textfont={"size": 11, "color": "#173f5f"},
        hovertext=node_hover, hovertemplate="%{hovertext}<extra></extra>",
        marker={"size": node_size, "color": node_color, "line": {"color": "#fffdf7", "width": 2}},
        showlegend=False,
    ))
    figure.update_layout(
        height=245, margin={"l": 15, "r": 15, "t": 8, "b": 36},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hovermode="closest", dragmode=False,
        xaxis={"visible": False, "range": [-0.35, 3.35], "fixedrange": True},
        yaxis={"visible": False, "range": [-0.92, 0.92], "fixedrange": True},
    )
    st.markdown("#### Governance participation")
    st.caption("Live decision path · muted roles were not invoked for this case · hover a role for its permitted contribution.")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})

def _render_agent_result(result: dict[str, Any]) -> None:
    """Present the agent contract as an analyst-readable result, not raw JSON."""
    if result.get("blocked"):
        st.error("Recommendation blocked: " + str(result.get("block_reason", "Safety check failed.")))
        return
    left, right = st.columns(2)
    with left:
        st.metric("Severity", result.get("severity") or "—")
        st.metric("Policy", result.get("policy_id") or "—")
    with right:
        st.metric("Route", result.get("recommended_queue") or "—")
        confidence = result.get("confidence")
        st.metric("Retrieval confidence", "—" if confidence is None else f"{float(confidence):.0%}")
    st.markdown("**Recommended action**")
    st.write(result.get("recommended_action") or "No action was produced.")
    if result.get("reason_codes"):
        st.markdown("**Reason codes:** " + " · ".join(str(item) for item in result["reason_codes"]))
    if result.get("citations"):
        st.markdown("**Policy citations:** " + " · ".join(str(item) for item in result["citations"]))
    if result.get("limitations"):
        st.caption(" · ".join(str(item) for item in result["limitations"]))

def _with_runtime_status(data: pd.DataFrame, store: RuntimeStore) -> pd.DataFrame:
    status_map = store.status_by_exception()
    frame = data.copy()
    frame["case_status"] = frame["exception_id"].map(status_map).fillna("NEW")
    return frame


def _load_lineage(exception_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Read the restricted Neo4j projection for the local analyst identity."""
    try:
        from contracts.access import AuthenticatedSession
        from governance.api import get_case_lineage, mint_access_context

        context = mint_access_context(AuthenticatedSession(user_id="ops_01"))
        return get_case_lineage(exception_id, context).model_dump(mode="json"), None
    except Exception as error:
        return None, str(error)


def _render_lineage_graph(lineage: dict[str, Any] | None, error: str | None = None) -> None:
    if lineage and lineage.get("nodes"):
        from governance.lineage_viz import build_lineage_figure

        st.plotly_chart(build_lineage_figure(lineage), width="stretch")
        st.caption("Neo4j decision lineage · hover nodes for permitted governed properties.")
    elif error:
        st.info("No governed decision lineage exists for this case yet. Run the governed recovery flow to create one.")
    else:
        st.info("No decision lineage is available yet.")

def _case_selector(data: pd.DataFrame, label: str = "Find a governed case", *, show_search: bool = True) -> str:
    selected = st.session_state.selected_exception_id
    query = ""
    if show_search:
        query = st.text_input(
            label,
            placeholder="Exception ID, transaction ID, masked client or masked card",
            key=f"case_search_{st.session_state.workspace_page}",
        )
    candidates = search_cases(data, query, limit=75)
    current = get_case(data, selected)
    if current is not None and selected not in set(candidates["exception_id"]):
        candidates = pd.concat([current.to_frame().T, candidates], ignore_index=True)
    options = candidates["exception_id"].astype(str).tolist()
    if not options:
        st.warning("No governed cases match that search.")
        return selected
    index = options.index(selected) if selected in options else 0
    lookup = candidates.set_index("exception_id")

    def label_case(exception_id: str) -> str:
        row = lookup.loc[exception_id]
        return (
            f"{exception_id}  ·  {display_exception_type(str(row['primary_exception_type']))}"
            f"  ·  {_money(row['amount'])}"
        )

    selected = st.selectbox(
        "Case",
        options,
        index=index,
        format_func=label_case,
        label_visibility="collapsed",
    )
    st.session_state.selected_exception_id = selected
    return selected


def _render_queue(data: pd.DataFrame, store: RuntimeStore) -> None:
    _page_header(
        "01 / INTAKE",
        "Exception Queue",
        "Search and prioritize the governed payment-exception inventory.",
    )
    status_data = _with_runtime_status(data, store)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Governed cases", f"{len(status_data):,}")
    metric_columns[1].metric(
        "Critical", f"{status_data['severity'].eq('CRITICAL').sum():,}"
    )
    metric_columns[2].metric(
        "Fraud context", f"{status_data['fraud_label'].eq('Yes').sum():,}"
    )
    metric_columns[3].metric(
        "Multi-error", f"{status_data['is_multi_error'].sum():,}"
    )

    st.markdown('<div class="section-label">Queue controls</div>', unsafe_allow_html=True)
    search = st.text_input(
        "Search queue",
        placeholder="Exception ID, transaction ID, masked client or masked card",
    )
    filter_columns = st.columns([1, 1.2, 1.2, 1])
    with filter_columns[0]:
        severity_filter = st.multiselect(
            "Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        )
    with filter_columns[1]:
        type_filter = st.multiselect(
            "Exception type",
            sorted(status_data["primary_exception_type"].dropna().unique()),
            format_func=display_exception_type,
        )
    with filter_columns[2]:
        queue_filter = st.multiselect(
            "Recommended queue",
            sorted(status_data["recommended_queue"].dropna().unique()),
        )
    with filter_columns[3]:
        status_filter = st.multiselect(
            "Decision state", ["NEW", "APPROVED", "REJECTED"]
        )

    filtered = status_data
    if search:
        filtered = search_cases(filtered, search, limit=len(filtered))
    if severity_filter:
        filtered = filtered.loc[filtered["severity"].isin(severity_filter)]
    if type_filter:
        filtered = filtered.loc[filtered["primary_exception_type"].isin(type_filter)]
    if queue_filter:
        filtered = filtered.loc[filtered["recommended_queue"].isin(queue_filter)]
    if status_filter:
        filtered = filtered.loc[filtered["case_status"].isin(status_filter)]
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    filtered = filtered.assign(
        _severity_rank=filtered["severity"].map(severity_rank)
    ).sort_values(["_severity_rank", "transaction_timestamp"], ascending=[True, False])

    page_size = 250
    filter_signature = (search, tuple(severity_filter), tuple(type_filter), tuple(queue_filter), tuple(status_filter))
    if st.session_state.get("queue_filter_signature") != filter_signature:
        st.session_state.queue_filter_signature = filter_signature
        st.session_state.queue_page = 0
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    current_page = min(st.session_state.get("queue_page", 0), total_pages - 1)
    st.session_state.queue_page = current_page
    start_row = current_page * page_size
    end_row = min(start_row + page_size, len(filtered))

    queue_columns = [
        "exception_id",
        "transaction_timestamp",
        "error_types",
        "severity",
        "amount",
        "recommended_queue",
        "case_status",
    ]
    page_cases = filtered.iloc[start_row:end_row]
    with st.container(border=True):
        st.dataframe(
            page_cases[queue_columns],
            width="stretch",
            hide_index=True,
            height=390,
            column_config={
                "exception_id": "Exception",
                "transaction_timestamp": st.column_config.DatetimeColumn(
                    "Occurred", format="YYYY-MM-DD HH:mm"
                ),
                "error_types": "Observed error",
                "severity": "Severity",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "recommended_queue": "Queue",
                "case_status": "Decision",
            },
        )
        navigation = st.columns([8, 0.45, 0.45])
        with navigation[1]:
            if st.button("‹", disabled=current_page == 0, width="stretch", key="queue_previous", help=f"Previous page · Page {current_page + 1:,} of {total_pages:,}"):
                st.session_state.queue_page = current_page - 1
                st.rerun()
        with navigation[2]:
            if st.button("›", disabled=current_page >= total_pages - 1, width="stretch", key="queue_next", help=f"Next page · Page {current_page + 1:,} of {total_pages:,}"):
                st.session_state.queue_page = current_page + 1
                st.rerun()
    open_options = page_cases["exception_id"].astype(str).tolist()
    if open_options:
        action_columns = st.columns([3, 1])
        with action_columns[0]:
            open_id = st.selectbox("Select a case to investigate", open_options)
        with action_columns[1]:
            st.write("")
            st.write("")
            st.button(
                "Open case →",
                type="primary",
                width="stretch",
                on_click=_navigate,
                args=("Case Investigation", open_id),
            )
    else:
        st.info("No cases match the current filters.")


def _render_case_data_lineage(case: pd.Series) -> None:
    """Render the selected case's Bronze-to-Gold provenance as an inspectable graph."""
    source_file = str(case.get("_source_file", "Unavailable source file"))
    pipeline_run_id = str(case.get("_pipeline_run_id", "Unavailable pipeline run"))
    ingested_at = str(case.get("_ingested_at_utc", "Unavailable ingest time"))
    bronze_row = int(case.get("_bronze_row_num", 0))
    grain = "one record per payment-exception case"
    nodes = [
        (0, "Source file", "#365b6d", f"<b>Source file</b><br>{source_file}"),
        (1, "Bronze record", "#8b6f47", f"<b>Bronze row number</b><br>{bronze_row}<br>Ingested at UTC: {ingested_at}"),
        (2, "Gold product", "#d4a72c", f"<b>finance_exception_case_gold</b><br>Grain: {grain}<br>Pipeline run: {pipeline_run_id}"),
        (3, str(case["exception_id"]), "#167d8d", f"<b>Case in review</b><br>{case['exception_id']}"),
    ]
    figure = go.Figure()
    for index in range(len(nodes) - 1):
        figure.add_trace(go.Scatter(x=[nodes[index][0], nodes[index + 1][0]], y=[0, 0], mode="lines", line={"color": "#9aa8ad", "width": 2}, hoverinfo="skip", showlegend=False))
    figure.add_trace(go.Scatter(
        x=[node[0] for node in nodes], y=[0] * len(nodes), mode="markers+text",
        text=[node[1] for node in nodes], textposition="top center", textfont={"size": 13, "color": "#132c3a"},
        hovertext=[node[3] for node in nodes], hovertemplate="%{hovertext}<extra></extra>",
        marker={"size": 34, "color": [node[2] for node in nodes], "line": {"color": "#fffdf7", "width": 2}}, showlegend=False,
    ))
    figure.update_layout(
        height=310, margin={"l": 20, "r": 20, "t": 35, "b": 20}, paper_bgcolor="#fffdf7", plot_bgcolor="#f7f4ec", hovermode="closest",
        xaxis={"visible": False, "range": [-0.35, 3.35], "fixedrange": True}, yaxis={"visible": False, "range": [-0.65, 0.65], "fixedrange": True},
        title={"text": "Source → Bronze → governed Gold → case", "x": 0.02, "font": {"size": 14, "color": "#132c3a"}},
    )
    st.plotly_chart(figure, width="stretch", config={"scrollZoom": False})
    st.caption("Hover a node for its governed provenance fields. Sensitive payment fields are excluded.")
    st.dataframe(pd.DataFrame([
        {"Provenance field": "Source file", "Value": source_file},
        {"Provenance field": "Pipeline run ID", "Value": pipeline_run_id},
        {"Provenance field": "Ingested at (UTC)", "Value": ingested_at},
        {"Provenance field": "Bronze row number", "Value": bronze_row},
        {"Provenance field": "Gold product", "Value": "finance_exception_case_gold"},
        {"Provenance field": "Grain", "Value": grain},
    ]), width="stretch", hide_index=True)

def _render_investigation(data: pd.DataFrame, store: RuntimeStore) -> None:
    _page_header(
        "02 / EVIDENCE",
        "Case Investigation",
        "Inspect masked evidence, explain severity, and run the ResolveOne agent with policy RAG.",
    )
    exception_id = _case_selector(data, show_search=False)
    case = get_case(data, exception_id)
    if case is None:
        st.error("The selected exception is not present in the Gold product.")
        return

    decision_status = store.status_by_exception().get(exception_id, "NEW")
    st.markdown(
        " ".join(
            [
                _badge(str(case["severity"]), _severity_tone(str(case["severity"]))),
                _badge(decision_status, "neutral"),
                _badge(str(case["recommended_queue"]), "queue"),
            ]
        ),
        unsafe_allow_html=True,
    )

    metrics = st.columns(4)
    metrics[0].metric("Amount", _money(case["amount"]))
    metrics[1].metric("Observed error", _format_value(case["error_types"]))
    metrics[2].metric("Card history", f"{int(case['card_exception_count']):,} exceptions")
    metrics[3].metric("Fraud label", _format_value(case["fraud_label"]))

    evidence_tab, history_tab, data_lineage_tab = st.tabs(
        ["Governed evidence", "Related card history", "Data lineage"]
    )
    with evidence_tab:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Transaction")
            st.write("**Exception ID**", case["exception_id"])
            st.write("**Transaction ID**", int(case["transaction_id"]))
            st.write("**Timestamp**", case["transaction_timestamp"])
            st.write("**Channel**", case["transaction_channel"])
            st.write("**Merchant category**", case["merchant_category"])
            st.write(
                "**Merchant location**",
                ", ".join(
                    part
                    for part in [
                        _format_value(case.get("merchant_city"), ""),
                        _format_value(case.get("merchant_state"), ""),
                    ]
                    if part
                )
                or "—",
            )
        with right:
            st.markdown("#### Protected payment profile")
            st.write("**Masked client**", case["masked_client_id"])
            st.write("**Masked card**", case["masked_card_id"])
            st.write("**Card**", f"{case['card_brand']} · {case['card_type']}")
            st.write("**Chip support**", "Yes" if bool(case["has_chip"]) else "No")
            st.write("**Credit limit**", _money(case["credit_limit"]))
            st.write(
                "**Dark-web indicator**",
                "Flagged" if bool(case["card_on_dark_web"]) else "Not flagged",
            )
        st.markdown("#### Explainable reason codes")
        st.markdown(
            " ".join(_badge(code, "reason") for code in reason_codes_for_case(case)),
            unsafe_allow_html=True,
        )

    with history_tab:
        related = data.loc[data["masked_card_id"].eq(case["masked_card_id"])].sort_values(
            "transaction_timestamp", ascending=False
        )
        st.caption(
            f"{len(related):,} governed exception records share this masked card ID."
        )
        st.dataframe(
            related[
                [
                    "exception_id",
                    "transaction_timestamp",
                    "error_types",
                    "severity",
                    "amount",
                ]
            ].head(50),
            width="stretch",
            hide_index=True,
        )

    with data_lineage_tab:
        st.markdown("#### Case data lineage")
        _render_case_data_lineage(case)

    st.markdown(
        """
        <section class="agent-lane">
            <div>
                <span>AGENT + RAG ENTRY POINT</span>
                <h3>ResolveOne Investigation Agent</h3>
                <p>LangGraph orchestrates the case workflow. The live service retrieves approved
                policy chunks from PostgreSQL + pgvector before producing a cited recommendation.</p>
            </div>
            <strong>HUMAN-GATED</strong>
        </section>
        """,
        unsafe_allow_html=True,
    )

    has_investigation = exception_id in st.session_state.investigation_results
    action_columns = st.columns([1, 1])
    with action_columns[0]:
        run_slot = st.empty()
        if run_slot.button(
            "Run ResolveOne agent + policy RAG",
            type="primary",
            width="stretch",
            disabled=has_investigation,
        ):
            _run_selected_investigation(exception_id, status_slot=run_slot)
            st.rerun()
    with action_columns[1]:
        st.button(
            "Review recommendation →",
            width="stretch",
            disabled=not has_investigation,
            on_click=_navigate,
            args=("Recommendation & Approval", exception_id),
        )
    if has_investigation:
        with st.container(border=True):
            _render_agent_result(st.session_state.investigation_results[exception_id])

    # Floating read-only decision-support assistant, intentionally separate from governed execution.
    with st.popover("✦  Ask ResolveOne", use_container_width=False):
        close_column = st.columns([5, 1])[1]
        with close_column:
            if st.button("×", key=f"chat_close_{exception_id}", width="stretch"):
                st.rerun()
        st.markdown(
            """
            <div class="agent-chat-intro">Ask about the selected exception, policy rationale,
            evidence, or why the case is routed. ResolveOne explains; governance decides.</div>
            """,
            unsafe_allow_html=True,
        )
        history_by_case = st.session_state.setdefault("chat_history", {})
        history = history_by_case.setdefault(exception_id, [])
        if history:
            _render_chat_history(history)
        st.markdown('<div class="agent-chat-suggestions">', unsafe_allow_html=True)
        suggestions = [
            "Why is this case routed here?",
            "Explain the policy requirement.",
            "What evidence supports this recommendation?",
        ]
        for index, suggestion in enumerate(suggestions):
            if st.button(suggestion, key=f"chat_suggestion_{exception_id}_{index}", width="stretch"):
                st.session_state[f"chat_input_{exception_id}"] = suggestion
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        chat_input = st.text_area(
            "Ask ResolveOne",
            placeholder="Ask about policy, evidence, or routing…",
            key=f"chat_input_{exception_id}",
            height=88,
            label_visibility="collapsed",
        )
        if st.button("Send message ↑", key=f"chat_send_{exception_id}", type="primary", width="stretch"):
            prompt = chat_input.strip() or "Explain this case and the applicable policy."
            history.append({"role": "user", "content": prompt})
            try:
                from contracts.access import AuthenticatedSession
                from governance.api import mint_access_context
                from chat.api import handle_chat
                from chat.schemas import ChatRequest

                access_context = mint_access_context(AuthenticatedSession(user_id="ops_01"))
                request = ChatRequest(text=prompt, exception_id=exception_id)
                response_payload = (
                    _call_member2_http(st.session_state["member2_url"], prompt, exception_id, access_context.model_dump(mode="json"))
                    if st.session_state.get("member2_url")
                    else handle_chat(request, access_context).model_dump(mode="json")
                )
                content, citations, notice = _chat_display(response_payload)
                history.append({"role": "assistant", "content": content, "citations": citations, "notice": notice})
            except Exception:
                history.append({"role": "assistant", "content": "The chat service is temporarily unavailable. Please try again.", "notice": "CHAT_SERVICE_UNAVAILABLE"})
            st.rerun()

def _render_recommendation(data: pd.DataFrame, store: RuntimeStore) -> None:
    _page_header(
        "03 / CONTROL",
        "Recommendation & Approval",
        "Review cited policy guidance and record a human decision before action.",
    )
    exception_id = _case_selector(data, show_search=False)
    case = get_case(data, exception_id)
    if case is None:
        st.error("The selected exception is not present in the Gold product.")
        return

    result = st.session_state.investigation_results.get(exception_id)
    if result is None:
        st.info("Run the governed investigation to produce a reviewable recommendation.")
        recommendation_run_slot = st.empty()
        if recommendation_run_slot.button("Run ResolveOne agent + policy RAG", type="primary", width="stretch"):
            _run_selected_investigation(exception_id, status_slot=recommendation_run_slot)
            st.rerun()
        result = st.session_state.investigation_results.get(exception_id)

    if result is None:
        return
    if result.get("blocked"):
        st.error(f"Recommendation blocked: {result.get('block_reason', 'safety check failed')}")
        st.json(result)
        return

    source_mode = result.get("source_mode", "unknown")
    if source_mode == "approved_policy_fallback":
        st.warning(
            "Approved-policy fallback active: severity and policy are deterministic, "
            "but live pgvector retrieval could not be evaluated."
        )
    else:
        st.success("LangGraph + pgvector result available.")

    summary_columns = st.columns(4)
    summary_columns[0].metric("Severity", result.get("severity") or "—")
    summary_columns[1].metric("Route", result.get("recommended_queue") or "—")
    summary_columns[2].metric("Policy", result.get("policy_id") or "—")
    confidence = result.get("confidence")
    summary_columns[3].metric(
        "Retrieval confidence",
        "Not scored" if confidence is None else f"{float(confidence):.0%}",
    )

    with st.container(border=True):
        st.markdown("### Recommended next action")
        st.write(result.get("recommended_action") or "No action was produced.")
        st.markdown("**Reason codes**")
        st.markdown(
            " ".join(_badge(code, "reason") for code in result.get("reason_codes", [])),
            unsafe_allow_html=True,
        )
        st.markdown("**Policy citations**")
        for citation in result.get("citations", []):
            st.code(citation, language=None)

    if result.get("limitations"):
        with st.expander("Known limitations", expanded=source_mode != "langgraph_pgvector"):
            for limitation in result["limitations"]:
                st.write(f"- {limitation}")

    st.markdown('<div class="approval-rail">Human approval checkpoint</div>', unsafe_allow_html=True)
    st.caption(
        "No payment retry, reversal, refund, balance change, or card action is executed by this UI."
    )
    current_status = store.status_by_exception().get(exception_id)
    if current_status:
        st.info(f"Latest recorded decision for {exception_id}: {current_status}")

    st.markdown("#### Governed recovery")
    st.caption("This runs the governed recovery path: investigate → authorize → execute → verify → receipt → Neo4j lineage.")
    recovery_by_case = st.session_state.setdefault("orchestration_results", {})
    recovery = recovery_by_case.get(exception_id)
    can_run_recovery = integration_process_event is not None or st.session_state.get("member3_url")
    recovery_slot = st.empty()
    if recovery_slot.button(
        "Run governed recovery",
        type="primary",
        disabled=not can_run_recovery or recovery is not None,
        help="Creates a governance receipt and Neo4j lineage, then performs only the policy-authorized controlled recovery action.",
    ):
        recovery_labels = {
            "start_investigation": "Investigating governed case…",
            "validate_contract": "Loading permitted evidence…",
            "fetch_evidence": "Calculating severity and route…",
            "score_severity_and_queue": "Retrieving approved policy…",
            "retrieve_policy": "Building cited recommendation…",
            "generate_recommendation": "Checking policy safeguards…",
            "verify_policy_and_safety": "Authorizing controlled action…",
            "require_human_approval": "Creating governance receipt…",
            "record_and_route": "Evaluating recovery eligibility…",
            "authorize_action": "Creating governance receipt…",
            "create_receipt": "Executing authorized recovery…",
            "sandbox_execution": "Verifying recovery outcome…",
            "verify_execution": "Finalizing governance receipt…",
            "finalize_receipt": "Loading Neo4j decision lineage…",
            "load_lineage": "Finalizing governed recovery…",
            "fake_recovery": "Running demo recovery adapter…",
        }
        def render_recovery_progress(step: str) -> None:
            recovery_slot.markdown(
                f'<div class="agent-run-progress"><span class="agent-run-spinner"></span><span>{recovery_labels.get(step, "Processing governed recovery…")}</span></div>',
                unsafe_allow_html=True,
            )
        event = {"exception_id": exception_id, "trace_id": f"TRACE-{exception_id}", "requester_user_id": "ops_01"}
        st.session_state.setdefault("recovery_requesters", {})[exception_id] = event["requester_user_id"]
        render_recovery_progress("start_investigation")
        try:
            recovery = (
                _call_member3_http(st.session_state["member3_url"], event)
                if st.session_state.get("member3_url")
                else integration_process_event(event, on_step=render_recovery_progress)
            )
            recovery_by_case[exception_id] = recovery
            st.rerun()
        except Exception as error:
            recovery_slot.error(f"Governed recovery could not complete: {error}")
    if recovery:
        status = str(recovery.get("status", "UNKNOWN")).replace("_", " ").title()
        st.success(f"Governed recovery finished: {status}")
        receipt = recovery.get("receipt") or {}
        status_columns = st.columns(3)
        status_columns[0].metric("Authorization", (recovery.get("authorization") or {}).get("decision", "—"))
        status_columns[1].metric("Receipt outcome", receipt.get("outcome", "—"))
        status_columns[2].metric("Execution", (recovery.get("execution") or {}).get("status", "Not executed"))
        requester_user_id = st.session_state.get("recovery_requesters", {}).get(exception_id, "ops_01")
        _render_workflow_role_panel(recovery, requester_user_id)
        if recovery.get("lineage"):
            _render_lineage_graph(recovery["lineage"])
    if recovery and recovery.get("status") == "PENDING_APPROVAL":
        st.warning("Manager approval required before governed execution can continue.")
        with st.form(f"governance_approval_{exception_id}", clear_on_submit=True):
            manager_decision = st.radio("Manager decision", ["APPROVE", "REJECT"], horizontal=True)
            manager_comment = st.text_area("Manager rationale", placeholder="Record the governed decision rationale.")
            resume_submitted = st.form_submit_button("Record manager decision and continue", type="primary", width="stretch")
        if resume_submitted:
            if not manager_comment.strip():
                st.error("A manager rationale is required.")
            elif integration_resume_pending_approval is None:
                st.error("The real governance approval service is unavailable.")
            else:
                try:
                    updated_recovery = integration_resume_pending_approval(recovery, manager_decision, manager_comment.strip())
                    recovery_by_case[exception_id] = updated_recovery
                    st.rerun()
                except Exception as error:
                    st.error(f"Governance approval could not be completed: {error}")
def _render_audit_metrics(data: pd.DataFrame, store: RuntimeStore) -> None:
    _page_header(
        "04 / PROOF",
        "Audit & Metrics",
        "Inspect measured pipeline quality, operational distributions, and analyst decisions.",
    )
    quality = _get_quality_results()
    tests = quality.get("quality_results", [])
    passed_tests = sum(bool(item.get("passed")) for item in tests)
    decisions = store.latest_decisions()
    events = store.latest_audit_events()
    prohibited = {"card_number", "cvv", "pin", "address", "latitude", "longitude"}
    leakage = prohibited & set(data.columns)

    metrics = st.columns(4)
    metrics[0].metric("Gold rows", f"{len(data):,}")
    metrics[1].metric("Quality checks", f"{passed_tests}/{len(tests)}")
    metrics[2].metric("Duplicate cases", f"{data['exception_id'].duplicated().sum():,}")
    metrics[3].metric("Sensitive fields exposed", str(len(leakage)))

    audit_tab, lineage_tab, distribution_tab, quality_tab, provenance_tab = st.tabs(
        ["Audit trail", "Decision lineage", "Measured distributions", "Data quality", "Provenance & limits"]
    )
    with audit_tab:
        st.markdown("#### Analyst decisions")
        if decisions:
            st.dataframe(pd.DataFrame(decisions), width="stretch", hide_index=True)
        else:
            st.info("No analyst decisions have been recorded yet.")
        st.markdown("#### Runtime events")
        if events:
            st.dataframe(pd.DataFrame(events), width="stretch", hide_index=True)
        else:
            st.caption("The audit event stream will populate after the first decision.")

    with lineage_tab:
        st.markdown("#### Neo4j governed decision lineage")
        audit_exception_id = _case_selector(
            data,
            label="Choose a case to inspect in the audit graph",
            show_search=False,
        )
        lineage, lineage_error = _load_lineage(audit_exception_id)
        _render_lineage_graph(lineage, lineage_error)
        st.caption("This graph is the immutable decision trail: evidence, policy, authorization, receipt, execution, and outcome.")
    with distribution_tab:
        left, right = st.columns(2)
        with left:
            counts = data["primary_exception_type"].value_counts().sort_values()
            fig = go.Figure(
                go.Bar(
                    x=counts.values,
                    y=[display_exception_type(value) for value in counts.index],
                    orientation="h",
                    marker_color="#167d8d",
                )
            )
            fig.update_layout(
                title="Exceptions by governed type",
                height=380,
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig, width="stretch")
        with right:
            severity = data["severity"].value_counts().reindex(
                ["CRITICAL", "HIGH", "MEDIUM", "LOW"], fill_value=0
            )
            fig = go.Figure(
                go.Pie(
                    labels=severity.index,
                    values=severity.values,
                    hole=0.62,
                    marker_colors=["#9b2c2c", "#c65d21", "#d4a72c", "#167d8d"],
                )
            )
            fig.update_layout(
                title="Deterministic severity mix",
                height=380,
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig, width="stretch")
        yearly = data.groupby(data["transaction_timestamp"].dt.year).size()
        st.markdown("#### Exception history by source year")
        st.line_chart(yearly.rename("Exceptions"), color="#d4a72c")
        st.caption(
            "These timestamps describe the public source dataset (2010–2019), "
            "not live operational traffic."
        )
    with quality_tab:
        if tests:
            quality_frame = pd.DataFrame(tests)
            quality_frame["status"] = quality_frame["passed"].map(
                {True: "PASS", False: "FAIL"}
            )
            st.dataframe(
                quality_frame[["test", "status"]],
                width="stretch",
                hide_index=True,
            )
        if quality.get("all_tests_passed"):
            st.success("All published pipeline quality checks passed.")
        else:
            st.warning("Published pipeline quality is incomplete or contains failures.")
        st.json(quality.get("metrics", {}))
    with provenance_tab:
        st.markdown("#### Governed source")
        st.code(str(DEFAULT_GOLD_PATH.resolve()), language=None)
        st.write("**Product:** finance_exception_case_gold")
        st.write("**Grain:** one record per payment-exception case")
        st.write("**Pipeline run:**", data["_pipeline_run_id"].iloc[0])
        st.write("**Current runtime persistence:** local SQLite adapter")
        st.markdown("#### Known limits")
        st.write("- Source transactions are historical public data, not a live payment feed.")
        st.write("- PostgreSQL/pgvector is required to evaluate live retrieval metrics.")
        st.write("- SQLite is the local demo fallback for decisions; production targets PostgreSQL.")
        st.write("- The UI never executes retries, refunds, reversals, or account/card changes.")


_load_css()
data = _get_data()
runtime_store = _get_runtime_store()

if "investigation_results" not in st.session_state:
    st.session_state.investigation_results = {}
if "orchestration_results" not in st.session_state:
    st.session_state.orchestration_results = {}
if "last_agent_mode" not in st.session_state:
    st.session_state.last_agent_mode = "not run"
if "selected_exception_id" not in st.session_state:
    technical = data.loc[data["primary_exception_type"].eq("TECHNICAL_GLITCH")]
    st.session_state.selected_exception_id = str(
        technical.iloc[0]["exception_id"] if not technical.empty else data.iloc[0]["exception_id"]
    )

PAGES = [
    "Exception Queue",
    "Case Investigation",
    "Recommendation & Approval",
    "Audit & Metrics",
]

st.sidebar.markdown(
    """
    <div class="brand-lockup">
        <div class="brand-mark">R1</div>
        <div><strong>ResolveOne</strong><span>Exception command desk</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)
page = st.sidebar.radio(
    "Workspace",
    PAGES,
    key="workspace_page",
    label_visibility="collapsed",
)
st.sidebar.markdown(
    f"""
    <div class="system-panel">
        <span class="system-label">GOVERNED GOLD</span>
        <strong>{len(data):,} cases</strong>
        <small>Pipeline {escape(str(data['_pipeline_run_id'].iloc[0]))}</small>
        <span class="system-label">AGENT + RAG MODE</span>
        <strong>{escape(str(st.session_state.last_agent_mode).replace('_', ' '))}</strong>
        <small>Controlled actions remain human-gated</small>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.caption("Masked evidence only · Runtime v1.1")

if page == "Exception Queue":
    _render_queue(data, runtime_store)
elif page == "Case Investigation":
    _render_investigation(data, runtime_store)
elif page == "Recommendation & Approval":
    _render_recommendation(data, runtime_store)
else:
    _render_audit_metrics(data, runtime_store)
