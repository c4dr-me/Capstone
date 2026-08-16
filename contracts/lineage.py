"""Small, UI-safe decision-lineage projection."""

from typing import Any

from .base import ContractModel


class LineageNode(ContractModel):
    id: str
    type: str
    label: str
    properties: dict[str, Any]


class LineageEdge(ContractModel):
    source: str
    target: str
    type: str


class CaseLineage(ContractModel):
    exception_id: str
    trace_id: str
    nodes: tuple[LineageNode, ...]
    edges: tuple[LineageEdge, ...]
    receipt_id: str
    completeness: float
