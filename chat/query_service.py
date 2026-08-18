"""Governed query and case lookup service for Member 2 chat."""

import os
import re
from typing import Any

import pandas as pd

from contracts.access import AccessContext


class AccessScopeError(ValueError):
    """Raised when a request attempts to escape the validated access scope."""


class QueryService:
    """Return only case data allowed by a validated AccessContext."""

    def __init__(self, gold_parquet_path: str | None = None, *, data: pd.DataFrame | None = None):
        self.gold_parquet_path = gold_parquet_path or os.getenv(
            "RESOLVEONE_GOLD_PARQUET", "data/processed/gold_exception_cases.parquet"
        )
        self._data = data

    def _load_data(self) -> pd.DataFrame:
        if self._data is None:
            if not os.path.exists(self.gold_parquet_path):
                raise FileNotFoundError("Governed case data is unavailable.")
            self._data = pd.read_parquet(self.gold_parquet_path)
        return self._data

    def _scoped_data(self, access_context: AccessContext) -> pd.DataFrame:
        df = self._load_data().copy()
        if "tenant_id" in df.columns:
            df = df[df["tenant_id"] == access_context.tenant_id]
        elif access_context.tenant_id != "TENANT-DEMO":
            return df.iloc[0:0]
        if not access_context.allowed_queues:
            return df.iloc[0:0]
        # Gold exposes fraud context, from which governance derives the canonical
        # queue. This keeps the chat scope aligned with the governance adapter.
        if "queue" not in df.columns:
            if "fraud_label" not in df.columns:
                raise ValueError("Governed case data is missing queue scope.")
            df["queue"] = df["fraud_label"].astype(str).eq("Yes").map(
                {True: "FRAUD", False: "OPERATIONS"}
            )
        return df[df["queue"].isin(access_context.allowed_queues)]

    @staticmethod
    def _project(df: pd.DataFrame, access_context: AccessContext) -> pd.DataFrame:
        if access_context.can_view_risk_fields:
            return df
        return df.drop(columns=[column for column in ("risk", "fraud_label") if column in df.columns])

    def get_case_in_scope(self, exception_id: str, access_context: AccessContext) -> dict[str, Any] | None:
        """Return a case only when it belongs to the caller's tenant and queue."""
        df = self._scoped_data(access_context)
        if "exception_id" not in df.columns:
            raise ValueError("Governed case data is missing exception identifiers.")
        rows = df[df["exception_id"] == exception_id]
        if rows.empty:
            return None
        return self._project(rows.head(1), access_context).to_dict("records")[0]

    def query_cases(
        self,
        access_context: AccessContext,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> tuple[int, tuple[dict[str, Any], ...]]:
        """Execute allowlisted filters after tenant and queue enforcement."""
        df = self._scoped_data(access_context)
        allowed = {"queue", "exception_type", "status", "risk", "severity", "amount_min"}
        if filters:
            if set(filters) - allowed:
                raise ValueError("Query contains an unsupported filter.")
            if "risk" in filters and not access_context.can_view_risk_fields:
                raise AccessScopeError("Risk filters require risk-field access.")
            for key, value in filters.items():
                if key == "amount_min":
                    if "amount" not in df.columns:
                        raise ValueError("Governed case data is missing amounts.")
                    df = df[df["amount"] >= float(value)]
                elif key not in df.columns:
                    raise ValueError("Governed case data is missing a supported filter field.")
                else:
                    df = df[df[key] == value]
        projected = self._project(df, access_context)
        capped_limit = max(1, min(int(limit), 100))
        return len(projected), tuple(projected.head(capped_limit).to_dict("records"))


def query_cases(
    text: str,
    access_context: AccessContext,
    gold_parquet_path: str | None = None,
    *,
    service: QueryService | None = None,
) -> tuple[int, tuple[dict[str, Any], ...]]:
    """Compile a small allowlisted query language; never interpret text as SQL."""
    service = service or QueryService(gold_parquet_path)
    filters: dict[str, Any] = {}
    text_lower = text.lower().replace("-", " ")
    if "high.risk" in text_lower or "high risk" in text_lower:
        filters["risk"] = "HIGH"
    elif "low.risk" in text_lower or "low risk" in text_lower:
        filters["risk"] = "LOW"
    if "technical" in text_lower:
        filters["exception_type"] = "TECHNICAL_GLITCH"
    if "unresolved" in text_lower:
        filters["status"] = "NEW"
    amount_match = re.search(r"(?:above|over|greater than)\s*\$?(\d+(?:\.\d+)?)", text_lower)
    if amount_match:
        filters["amount_min"] = float(amount_match.group(1))
    return service.query_cases(access_context, filters=filters)