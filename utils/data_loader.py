"""Governed data adapter for the ResolveOne Streamlit application.

The UI reads Member 1's published Gold parquet only. It never reaches into
raw data and it never manufactures transaction records. The adapter adds
deterministic, explainable presentation fields (severity and queue) without
mutating the governed source artifact.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLD_PATH = REPO_ROOT / "data" / "processed" / "gold_exception_cases.parquet"
DEFAULT_QUALITY_PATH = REPO_ROOT / "data" / "processed" / "quality_results.json"

REQUIRED_GOLD_COLUMNS = {
    "exception_id",
    "transaction_id",
    "transaction_timestamp",
    "masked_client_id",
    "masked_card_id",
    "amount",
    "transaction_channel",
    "merchant_category",
    "error_types",
    "is_multi_error",
    "fraud_label",
    "_source_file",
    "_ingested_at_utc",
    "_pipeline_run_id",
}

ERROR_TYPE_ALIASES = {
    "insufficient balance": "INSUFFICIENT_BALANCE",
    "bad pin": "BAD_PIN",
    "technical glitch": "TECHNICAL_GLITCH",
    "bad card number": "BAD_CARD_NUMBER",
    "bad expiration": "BAD_EXPIRATION",
    "bad cvv": "BAD_CVV",
    "bad zipcode": "BAD_ZIPCODE",
}

BASE_SEVERITY = {
    "INSUFFICIENT_BALANCE": "LOW",
    "BAD_PIN": "MEDIUM",
    "TECHNICAL_GLITCH": "HIGH",
    "BAD_CARD_NUMBER": "MEDIUM",
    "BAD_EXPIRATION": "MEDIUM",
    "BAD_CVV": "HIGH",
    "BAD_ZIPCODE": "LOW",
}

QUEUE_BY_TYPE = {
    "INSUFFICIENT_BALANCE": "Customer Payment Support",
    "BAD_PIN": "Card Support",
    "TECHNICAL_GLITCH": "Payment Operations",
    "BAD_CARD_NUMBER": "Payment Validation",
    "BAD_EXPIRATION": "Card Support",
    "BAD_CVV": "Card Security Review",
    "BAD_ZIPCODE": "Payment Validation",
}

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SEVERITY_INDEX = {name: index for index, name in enumerate(SEVERITY_ORDER)}


def _configured_gold_path() -> Path:
    configured = os.environ.get("RESOLVEONE_GOLD_PARQUET") or os.environ.get(
        "DATA_PROCESSED_GOLD"
    )
    if not configured:
        return DEFAULT_GOLD_PATH
    candidate = Path(configured)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _canonical_components(raw_error_types: Any) -> list[str]:
    return [
        ERROR_TYPE_ALIASES[part.strip().lower()]
        for part in str(raw_error_types).split(",")
        if part.strip().lower() in ERROR_TYPE_ALIASES
    ]


def _primary_exception_type(raw_error_types: Any) -> str:
    components = _canonical_components(raw_error_types)
    if not components:
        return "UNKNOWN"
    return max(
        components,
        key=lambda item: SEVERITY_INDEX[BASE_SEVERITY[item]],
    )


def _add_operational_fields(gold: pd.DataFrame) -> pd.DataFrame:
    frame = gold.copy()
    frame["transaction_timestamp"] = pd.to_datetime(
        frame["transaction_timestamp"], errors="coerce", utc=True
    )
    frame["primary_exception_type"] = frame["error_types"].map(
        _primary_exception_type
    )
    frame["card_exception_count"] = frame.groupby("masked_card_id")[
        "exception_id"
    ].transform("size")

    base_index = (
        frame["primary_exception_type"]
        .map(BASE_SEVERITY)
        .map(SEVERITY_INDEX)
        .fillna(0)
        .astype("int8")
    )
    escalation_count = (
        frame["amount"].ge(250).fillna(False).astype("int8")
        + frame["is_multi_error"].fillna(False).astype("int8")
        + frame["card_exception_count"].ge(3).astype("int8")
    )
    severity_index = np.minimum(base_index + escalation_count, 3)
    severity_index = pd.Series(severity_index, index=frame.index)
    severity_index.loc[frame["fraud_label"].eq("Yes")] = 3

    frame["severity"] = severity_index.map(dict(enumerate(SEVERITY_ORDER)))
    frame["recommended_queue"] = frame["primary_exception_type"].map(
        QUEUE_BY_TYPE
    )
    frame.loc[
        frame["fraud_label"].eq("Yes"), "recommended_queue"
    ] = "Fraud Analyst"
    frame["case_status"] = "NEW"
    return frame


@lru_cache(maxsize=2)
def _load_gold_cached(path_string: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    path = Path(path_string)
    gold = pd.read_parquet(path)
    missing = sorted(REQUIRED_GOLD_COLUMNS - set(gold.columns))
    if missing:
        raise ValueError(f"Gold data is missing required columns: {missing}")
    if gold["exception_id"].isna().any() or gold["exception_id"].duplicated().any():
        raise ValueError("Gold exception_id must be non-null and unique")
    return _add_operational_fields(gold)


def load_gold_data(path: str | Path | None = None) -> pd.DataFrame:
    """Load the governed Gold product and add deterministic UI fields."""

    resolved = Path(path) if path is not None else _configured_gold_path()
    resolved = resolved.resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"Governed Gold data not found at {resolved}. "
            "Set RESOLVEONE_GOLD_PARQUET or DATA_PROCESSED_GOLD."
        )
    return _load_gold_cached(str(resolved), resolved.stat().st_mtime_ns)


def load_sample_data() -> pd.DataFrame:
    """Backward-compatible alias; no synthetic data is generated."""

    return load_gold_data()


def load_quality_results(path: str | Path | None = None) -> dict[str, Any]:
    resolved = Path(path) if path is not None else DEFAULT_QUALITY_PATH
    resolved = resolved.resolve()
    if not resolved.exists():
        return {
            "all_tests_passed": False,
            "quality_results": [],
            "metrics": {},
            "limitation": f"Quality results not found at {resolved}",
        }
    return json.loads(resolved.read_text(encoding="utf-8"))


def get_case(df: pd.DataFrame, exception_id: str) -> pd.Series | None:
    matches = df.loc[df["exception_id"].eq(exception_id)]
    return None if matches.empty else matches.iloc[0]


def reason_codes_for_case(case: pd.Series) -> list[str]:
    codes = [str(case["primary_exception_type"])]
    if pd.notna(case["amount"]) and float(case["amount"]) >= 250:
        codes.append("HIGH_VALUE_TRANSACTION")
    if bool(case["is_multi_error"]):
        codes.append("MULTI_ERROR_CASE")
    if str(case["fraud_label"]) == "Yes":
        codes.append("FRAUD_CONTEXT_PRESENT")
    if int(case["card_exception_count"]) >= 3:
        codes.append("REPEATED_EXCEPTIONS_ON_CARD")
    return codes


def search_cases(df: pd.DataFrame, query: str, limit: int = 100) -> pd.DataFrame:
    query = query.strip()
    if not query:
        return df.head(limit)
    mask = (
        df["exception_id"].astype("string").str.contains(query, case=False, na=False)
        | df["transaction_id"]
        .astype("string")
        .str.contains(query, case=False, na=False)
        | df["masked_client_id"]
        .astype("string")
        .str.contains(query, case=False, na=False)
        | df["masked_card_id"]
        .astype("string")
        .str.contains(query, case=False, na=False)
    )
    return df.loc[mask].head(limit)


def display_exception_type(value: str) -> str:
    return value.replace("_", " ").title()
