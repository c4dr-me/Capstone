"""Persistent local runtime store for analyst decisions and audit events.

The production target remains PostgreSQL.  SQLite keeps the live capstone UI
functional when the VM service lane is unavailable and can be replaced behind
this small interface without changing the screens.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "runtime" / "resolveone_runtime.db"


class RuntimeStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get("RESOLVEONE_RUNTIME_DB") or DEFAULT_DB_PATH
        self.path = Path(configured).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyst_decisions (
                    decision_id TEXT PRIMARY KEY,
                    exception_id TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED')),
                    analyst_reason TEXT NOT NULL,
                    approval_timestamp TEXT NOT NULL,
                    agent_trace_id TEXT NOT NULL,
                    recommendation_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    exception_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    agent_trace_id TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS analyst_decisions_exception_idx
                    ON analyst_decisions(exception_id, approval_timestamp DESC);
                CREATE INDEX IF NOT EXISTS audit_events_exception_idx
                    ON audit_events(exception_id, created_at DESC);
                """
            )

    def record_decision(
        self,
        exception_id: str,
        decision: str,
        analyst_reason: str,
        recommendation: dict[str, Any],
        actor: str = "Finance Operations Analyst",
    ) -> dict[str, str]:
        normalized = decision.strip().upper()
        if normalized not in {"APPROVED", "REJECTED"}:
            raise ValueError("decision must be APPROVED or REJECTED")
        reason = analyst_reason.strip()
        if not reason:
            raise ValueError("analyst_reason is required")

        timestamp = datetime.now(timezone.utc).isoformat()
        decision_id = f"DEC-{uuid.uuid4().hex[:12].upper()}"
        trace_id = f"TRACE-{uuid.uuid4().hex[:12].upper()}"
        event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        details = f"Recommendation {normalized.lower()}: {reason}"

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analyst_decisions (
                    decision_id, exception_id, decision, analyst_reason,
                    approval_timestamp, agent_trace_id, recommendation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    exception_id,
                    normalized,
                    reason,
                    timestamp,
                    trace_id,
                    json.dumps(recommendation, default=str, sort_keys=True),
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, exception_id, event_type, actor, details,
                    created_at, agent_trace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    exception_id,
                    f"RECOMMENDATION_{normalized}",
                    actor,
                    details,
                    timestamp,
                    trace_id,
                ),
            )

        return {
            "decision_id": decision_id,
            "agent_trace_id": trace_id,
            "approval_timestamp": timestamp,
            "decision": normalized,
        }

    def latest_decisions(self, limit: int = 250) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT decision_id, exception_id, decision, analyst_reason,
                       approval_timestamp, agent_trace_id
                FROM analyst_decisions
                ORDER BY approval_timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_audit_events(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, exception_id, event_type, actor, details,
                       created_at, agent_trace_id
                FROM audit_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def status_by_exception(self) -> dict[str, str]:
        status: dict[str, str] = {}
        for row in self.latest_decisions(limit=10_000):
            status.setdefault(row["exception_id"], row["decision"])
        return status
