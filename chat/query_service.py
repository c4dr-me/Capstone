"""QUERY intent handler: governed case retrieval with access scope enforcement."""

import os
from typing import Any

import pandas as pd

from contracts.access import AccessContext


class QueryService:
    """Governed query service: returns case results scoped to user's access."""

    def __init__(self, gold_parquet_path: str | None = None):
        """Initialize with path to governed Gold case data.

        Args:
            gold_parquet_path: path to gold_exception_cases.parquet (defaults to env var)
        """
        self.gold_parquet_path = gold_parquet_path or os.getenv(
            "RESOLVEONE_GOLD_PARQUET", "data/processed/gold_exception_cases.parquet"
        )
        self._data: pd.DataFrame | None = None

    def _load_data(self) -> pd.DataFrame:
        """Lazy load the Gold case data."""
        if self._data is None:
            if not os.path.exists(self.gold_parquet_path):
                raise FileNotFoundError(f"Gold data not found at {self.gold_parquet_path}")
            self._data = pd.read_parquet(self.gold_parquet_path)
        return self._data

    def query_cases(
        self,
        access_context: AccessContext,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> tuple[int, tuple[dict[str, Any], ...]]:
        """Execute a governed query within user's scope.

        Args:
            access_context: validated AccessContext (provides tenant, queues, risk_field_flag)
            filters: allowlisted filter dict (only queue, risk, status, exception_type keys allowed)
            limit: max result count (capped at 100)

        Returns:
            (total_count, results_tuple)

        Raises:
            ValueError: if filters contain disallowed keys
        """
        data = self._load_data()

        # Enforce tenant scope (single tenant in hackathon)
        df = data.copy()

        # Enforce queue scope
        if access_context.allowed_queues:
            df = df[df["queue"].isin(access_context.allowed_queues)]

        # Apply allowlisted filters
        allowlisted_keys = {"queue", "exception_type", "status", "risk", "severity"}
        if filters:
            bad_keys = set(filters.keys()) - allowlisted_keys
            if bad_keys:
                raise ValueError(f"Disallowed filter keys: {bad_keys}")
            for key, value in filters.items():
                df = df[df[key] == value]

        # Mask risk fields if user cannot view them
        if not access_context.can_view_risk_fields:
            df = df.drop(columns=[col for col in ["risk", "fraud_label"] if col in df.columns])

        # Limit and convert to results
        limit = min(limit, 100)
        results = tuple(df.head(limit).to_dict("records"))

        return len(df), results


def query_cases(
    text: str,
    access_context: AccessContext,
    gold_parquet_path: str | None = None,
) -> tuple[int, tuple[dict[str, Any], ...]]:
    """Parse natural-language query and return governed results.

    Args:
        text: query text (e.g., "Show my high-risk cases")
        access_context: user's access scope
        gold_parquet_path: optional path to Gold data

    Returns:
        (count, results)
    """
    service = QueryService(gold_parquet_path)

    # Parse common query patterns
    filters = {}
    text_lower = text.lower()

    if "high.risk" in text_lower or "high risk" in text_lower:
        filters["risk"] = "HIGH"
    elif "low.risk" in text_lower or "low risk" in text_lower:
        filters["risk"] = "LOW"

    if "technical" in text_lower:
        filters["exception_type"] = "TECHNICAL_GLITCH"

    if "unresolved" in text_lower:
        filters["status"] = "NEW"

    return service.query_cases(access_context, filters=filters)
