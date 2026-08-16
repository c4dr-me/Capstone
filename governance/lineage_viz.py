"""Small, dependency-free-from-the-project interactive lineage projection."""

from __future__ import annotations

from collections import defaultdict
from html import escape
import re
from typing import Any, Mapping

import plotly.graph_objects as go


TYPE_COLUMNS = {
    "Transaction": 0,
    "Exception": 1,
    "EvidenceSnapshot": 2,
    "Agent": 2,
    "User": 2,
    "Role": 2,
    "ProposedAction": 3,
    "PolicyVersion": 3,
    "AuthorizationDecision": 4,
    "Approval": 5,
    "GovernanceReceipt": 5,
    "ReceiptRevision": 6,
    "ExecutionAttempt": 6,
    "Outcome": 7,
}

TYPE_COLORS = {
    "Transaction": "#365b6d",
    "Exception": "#c65d21",
    "EvidenceSnapshot": "#8b6f47",
    "Agent": "#6a5a8c",
    "User": "#167d8d",
    "Role": "#5996a0",
    "ProposedAction": "#d4a72c",
    "PolicyVersion": "#766a4e",
    "AuthorizationDecision": "#9b2c2c",
    "Approval": "#3f7d58",
    "GovernanceReceipt": "#173f5f",
    "ReceiptRevision": "#4f6d7a",
    "ExecutionAttempt": "#795548",
    "Outcome": "#2f855a",
}


def _words(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value).replace("_", " ")


def _payload(lineage: Any) -> dict[str, Any]:
    if hasattr(lineage, "model_dump"):
        return lineage.model_dump(mode="json")
    if isinstance(lineage, Mapping):
        return dict(lineage)
    raise TypeError("lineage must be a CaseLineage or mapping")


def _positions(nodes: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    columns: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        columns[TYPE_COLUMNS.get(str(node.get("type")), 4)].append(node)

    positions: dict[str, tuple[float, float]] = {}
    for column, members in columns.items():
        ordered = sorted(members, key=lambda item: (str(item.get("type")), str(item.get("id"))))
        count = len(ordered)
        for index, node in enumerate(ordered):
            y = (count - 1) / 2 - index
            positions[str(node["id"])] = (float(column), float(y))
    return positions


def build_lineage_figure(lineage: Any) -> go.Figure:
    """Create a pan/zoom/hover graph from the restricted lineage projection."""
    payload = _payload(lineage)
    nodes = [dict(node) for node in payload.get("nodes", [])]
    edges = [dict(edge) for edge in payload.get("edges", [])]
    positions = _positions(nodes)

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    label_x: list[float] = []
    label_y: list[float] = []
    label_text: list[str] = []
    for edge in edges:
        source = positions.get(str(edge.get("source")))
        target = positions.get(str(edge.get("target")))
        if source is None or target is None:
            continue
        edge_x.extend([source[0], target[0], None])
        edge_y.extend([source[1], target[1], None])
        label_x.append((source[0] + target[0]) / 2)
        label_y.append((source[1] + target[1]) / 2 + 0.08)
        label_text.append(str(edge.get("type", "")))

    node_x: list[float] = []
    node_y: list[float] = []
    node_text: list[str] = []
    hover_text: list[str] = []
    node_colors: list[str] = []
    for node in nodes:
        node_id = str(node.get("id", ""))
        if node_id not in positions:
            continue
        node_type = str(node.get("type", "Node"))
        node_x.append(positions[node_id][0])
        node_y.append(positions[node_id][1])
        node_text.append(_words(str(node.get("label") or node_type)))
        node_colors.append(TYPE_COLORS.get(node_type, "#6b7280"))
        properties = dict(node.get("properties") or {})
        detail = [f"<b>{escape(_words(node_type))}</b>", escape(node_id)]
        detail.extend(
            f"{escape(_words(str(key)))}: {escape(str(value))}"
            for key, value in sorted(properties.items())
            if value is not None
        )
        hover_text.append("<br>".join(detail))

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"color": "#9aa8ad", "width": 1.6},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=label_x,
            y=label_y,
            mode="text",
            text=label_text,
            textfont={"size": 9, "color": "#52636a"},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition="top center",
            textfont={"size": 11, "color": "#1a2c34"},
            hovertext=hover_text,
            hovertemplate="%{hovertext}<extra></extra>",
            marker={
                "size": 29,
                "color": node_colors,
                "line": {"color": "#fffdf7", "width": 2},
            },
            showlegend=False,
        )
    )
    figure.update_layout(
        height=590,
        margin={"l": 30, "r": 30, "t": 45, "b": 25},
        paper_bgcolor="#fffdf7",
        plot_bgcolor="#f7f4ec",
        hovermode="closest",
        dragmode="pan",
        xaxis={"visible": False, "range": [-0.45, 7.45], "fixedrange": False},
        yaxis={"visible": False, "fixedrange": False},
        title={
            "text": "Decision lineage · hover for governed properties · drag to pan · scroll to zoom",
            "x": 0.02,
            "font": {"size": 14, "color": "#1a2c34"},
        },
    )
    return figure
