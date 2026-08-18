"""Simple synthetic event producer for Member 3 demos."""
from __future__ import annotations

import json
import time
from typing import Dict, Any


def make_payment_exception_event(exception_id: str, case: Dict[str, Any] | None = None) -> Dict[str, Any]:
    event = {
        "event_id": f"EVT-{int(time.time())}",
        "event_type": "PAYMENT_EXCEPTION_CREATED",
        "exception_id": exception_id,
        "trace_id": f"TRACE-{exception_id}",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if case:
        event["case"] = case
    return event
