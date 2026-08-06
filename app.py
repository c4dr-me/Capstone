"""ResolveOne operations interface backed by the governed Gold data product."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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


def _run_selected_investigation(exception_id: str) -> dict[str, Any]:
    with st.spinner("Running governed evidence, severity, policy, and safety checks..."):
        result = run_investigation(exception_id)
    st.session_state.investigation_results[exception_id] = result
    st.session_state.last_agent_mode = result.get("source_mode", "unknown")
    return result


def _with_runtime_status(data: pd.DataFrame, store: RuntimeStore) -> pd.DataFrame:
    status_map = store.status_by_exception()
    frame = data.copy()
    frame["case_status"] = frame["exception_id"].map(status_map).fillna("NEW")
    return frame


def _case_selector(data: pd.DataFrame, label: str = "Find a governed case") -> str:
    selected = st.session_state.selected_exception_id
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

    st.caption(
        f"Showing up to 250 of {len(filtered):,} matching governed cases. "
        "Only masked identifiers are exposed."
    )
    queue_columns = [
        "exception_id",
        "transaction_timestamp",
        "error_types",
        "severity",
        "amount",
        "recommended_queue",
        "case_status",
    ]
    st.dataframe(
        filtered[queue_columns].head(250),
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

    open_options = filtered["exception_id"].head(100).astype(str).tolist()
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


def _render_investigation(data: pd.DataFrame, store: RuntimeStore) -> None:
    _page_header(
        "02 / EVIDENCE",
        "Case Investigation",
        "Inspect masked evidence, explain severity, and run the ResolveOne agent with policy RAG.",
    )
    exception_id = _case_selector(data)
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

    evidence_tab, history_tab, lineage_tab = st.tabs(
        ["Governed evidence", "Related card history", "Lineage"]
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
    with lineage_tab:
        lineage = {
            "source_file": case["_source_file"],
            "pipeline_run_id": case["_pipeline_run_id"],
            "ingested_at_utc": case["_ingested_at_utc"],
            "bronze_row_number": int(case["_bronze_row_num"]),
            "gold_product": "finance_exception_case_gold",
            "grain": "one record per payment-exception case",
        }
        st.json(lineage)
        st.success("Identifiers are masked; full card number and CVV are absent from Gold.")

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

    action_columns = st.columns([1, 1])
    with action_columns[0]:
        if st.button(
            "Run ResolveOne agent + policy RAG",
            type="primary",
            width="stretch",
        ):
            result = _run_selected_investigation(exception_id)
            if result.get("source_mode") == "langgraph_pgvector":
                st.success("ResolveOne agent completed with live pgvector policy RAG.")
            else:
                st.warning(
                    "Policy RAG is offline because the VM PostgreSQL/pgvector service is unavailable. "
                    "The agent returned its approved-policy deterministic fallback; vector retrieval "
                    "was not scored."
                )
    with action_columns[1]:
        st.button(
            "Review recommendation →",
            width="stretch",
            on_click=_navigate,
            args=("Recommendation & Approval", exception_id),
        )

    result = st.session_state.investigation_results.get(exception_id)
    if result:
        with st.expander("Latest structured investigation result", expanded=True):
            st.json(result)


def _render_recommendation(data: pd.DataFrame, store: RuntimeStore) -> None:
    _page_header(
        "03 / CONTROL",
        "Recommendation & Approval",
        "Review cited policy guidance and record a human decision before action.",
    )
    exception_id = _case_selector(data, "Choose the case awaiting decision")
    case = get_case(data, exception_id)
    if case is None:
        st.error("The selected exception is not present in the Gold product.")
        return

    result = st.session_state.investigation_results.get(exception_id)
    if result is None:
        st.info("Run the governed investigation to produce a reviewable recommendation.")
        if st.button("Run investigation now", type="primary"):
            result = _run_selected_investigation(exception_id)

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

    with st.form("analyst_decision_form", clear_on_submit=True):
        decision = st.radio("Decision", ["APPROVED", "REJECTED"], horizontal=True)
        reason = st.text_area(
            "Analyst reason",
            placeholder="Record the evidence-based reason for this controlled decision.",
        )
        submitted = st.form_submit_button(
            "Record decision", type="primary", width="stretch"
        )
    if submitted:
        if not reason.strip():
            st.error("An analyst reason is required for the audit trail.")
        else:
            receipt = store.record_decision(
                exception_id=exception_id,
                decision=decision,
                analyst_reason=reason,
                recommendation=result,
            )
            st.success(
                f"{decision.title()} and recorded with trace {receipt['agent_trace_id']}."
            )


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

    audit_tab, distribution_tab, quality_tab, provenance_tab = st.tabs(
        ["Audit trail", "Measured distributions", "Data quality", "Provenance & limits"]
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
        if st.session_state.investigation_results:
            with st.expander("Session investigation traces"):
                st.json(st.session_state.investigation_results)
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
