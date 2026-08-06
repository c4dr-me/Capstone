"""Governed evidence readers.

These are the only agent functions that touch a data file, and they read
exclusively from Member 1's published Gold product
(`data/processed/gold_exception_cases.parquet`). Raw source files under
`data/raw/` are never opened by agent code — enforced by
tests/agent/test_evidence_boundary.py. CVV and full card numbers do not exist
in Gold at all, so there is nothing here to filter; this module additionally
never selects `_source_file`/`_bronze_row_num` audit columns into evidence
returned to callers, since those are pipeline-internal, not case evidence.
"""

import functools

import pandas as pd

from agent.config import GOLD_PARQUET_PATH

CASE_EVIDENCE_COLUMNS = [
    "exception_id",
    "transaction_id",
    "transaction_timestamp",
    "masked_client_id",
    "masked_card_id",
    "amount",
    "transaction_channel",
    "merchant_category",
    "merchant_state",
    "error_types",
    "is_multi_error",
    "fraud_label",
    "card_brand",
    "card_type",
    "has_chip",
    "credit_limit",
    "card_on_dark_web",
]


@functools.lru_cache(maxsize=1)
def _load_gold() -> pd.DataFrame:
    return pd.read_parquet(GOLD_PARQUET_PATH)


def get_exception_case(exception_id: str) -> dict | None:
    df = _load_gold()
    matches = df[df["exception_id"] == exception_id]
    if matches.empty:
        return None
    row = matches.iloc[0]
    return {col: row[col] for col in CASE_EVIDENCE_COLUMNS if col in row.index}


def get_transaction_evidence(transaction_id: int) -> dict | None:
    df = _load_gold()
    matches = df[df["transaction_id"] == transaction_id]
    if matches.empty:
        return None
    row = matches.iloc[0]
    return {col: row[col] for col in CASE_EVIDENCE_COLUMNS if col in row.index}


def get_payment_profile(masked_card_id: str) -> dict:
    """Derives a lightweight golden-payment-profile aggregate on the fly from
    Gold, in the absence of a published golden_payment_profile.parquet from
    Member 1. Returns exception history for the masked card, used by the
    severity engine's repeated-exceptions escalation rule.
    """
    df = _load_gold()
    matches = df[df["masked_card_id"] == masked_card_id]
    return {
        "masked_card_id": masked_card_id,
        "historical_exception_count": int(len(matches)),
        "historical_fraud_flagged_count": int((matches["fraud_label"] == "Yes").sum()),
        "card_brand": matches.iloc[0]["card_brand"] if not matches.empty else None,
        "card_type": matches.iloc[0]["card_type"] if not matches.empty else None,
        "card_on_dark_web": bool(matches.iloc[0]["card_on_dark_web"]) if not matches.empty else None,
    }
