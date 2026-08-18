"""Fake lineage adapter returning a simple decision path projection."""
from __future__ import annotations

from typing import Dict


def get_case_lineage(exception_id: str, access_context: Dict) -> Dict:
    return {
        "exception_id": exception_id,
        "trace_id": "TRACE-FAKE",
        "nodes": [
            {"id": "tx", "type": "Transaction"},
            {"id": "exc", "type": "Exception"},
            {"id": "evd", "type": "Evidence"},
        ],
        "edges": [],
        "receipt_id": None,
        "completeness": 0.5,
    }
