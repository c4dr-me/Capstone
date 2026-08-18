"""Sandbox retry service: simulates a payment retry without contacting real rails."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict


def retry_payment(request: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic sandbox: return SUCCESS for exception IDs ending with an odd char, else FAILED."""
    exception_id = request.get("exception_id", "")
    case = request.get("case") or {}
    # If the case explicitly has a LOW severity, prefer SUCCESS for demo purposes
    try:
        severity = str(case.get("severity", "")).upper()
    except Exception:
        severity = ""
    if severity == "LOW":
        status = "SUCCESS"
    else:
    # simple deterministic rule
        last = exception_id[-1] if exception_id else "0"
        status = "SUCCESS" if ord(last) % 2 == 1 else "FAILED"
    reference = f"SIM-{uuid.uuid4().hex[:8]}"
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    time.sleep(0.1)
    completed = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "execution_id": request.get("execution_id"),
        "trace_id": request.get("trace_id"),
        "exception_id": exception_id,
        "action": request.get("action"),
        "status": status,
        "reference": reference,
        "verified": True,
        "started_at": started,
        "completed_at": completed,
    }
