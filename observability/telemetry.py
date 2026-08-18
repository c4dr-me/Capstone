"""Simple telemetry writer for Member 3 workflows."""
from __future__ import annotations

import json
from pathlib import Path
from time import time
from typing import Any, Dict

REPORTS_DIR = Path("reports") / "orchestration"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_FILE = REPORTS_DIR / "runtime_results.json"


def record_workflow_result(result: Dict[str, Any]) -> None:
    entry = {
        "trace_id": result.get("trace_id"),
        "exception_id": result.get("exception_id"),
        "status": result.get("status"),
        "timestamp": int(time()),
        "short_summary": {
            "authorization": result.get("authorization", {}).get("decision"),
            "outcome": result.get("execution", {}).get("status") if result.get("execution") else None,
        },
        "raw": result,
    }
    data = []
    if RUNTIME_FILE.exists():
        try:
            data = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data.append(entry)
    RUNTIME_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
