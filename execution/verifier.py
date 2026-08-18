"""Execution verifier: perform simple checks on ExecutionResult."""
from __future__ import annotations

from typing import Dict


def verify_execution(exec_result: Dict) -> bool:
    # Basic verification: must have status and reference
    if not exec_result:
        return False
    return bool(exec_result.get("status") and exec_result.get("reference"))
