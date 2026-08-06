from pathlib import Path

import pandas as pd

from utils.data_loader import (
    DEFAULT_GOLD_PATH,
    _add_operational_fields,
    load_gold_data,
    reason_codes_for_case,
)


def _gold_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "exception_id": ["EXC-1", "EXC-2", "EXC-3"],
            "transaction_id": [1, 2, 3],
            "transaction_timestamp": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03"], utc=True
            ),
            "masked_client_id": ["CLIENT-A"] * 3,
            "masked_card_id": ["CARD-A"] * 3,
            "amount": [100.0, 300.0, 10.0],
            "transaction_channel": ["Online Transaction"] * 3,
            "merchant_category": ["Utilities"] * 3,
            "error_types": [
                "Technical Glitch",
                "Insufficient Balance",
                "Bad Zipcode",
            ],
            "is_multi_error": [False, False, False],
            "fraud_label": ["No", "No", "Yes"],
            "_source_file": ["transactions_data.csv"] * 3,
            "_ingested_at_utc": ["2026-01-04T00:00:00Z"] * 3,
            "_pipeline_run_id": ["RUN-1"] * 3,
        }
    )


def test_operational_fields_follow_agent_rules():
    result = _add_operational_fields(_gold_fixture())

    assert result.loc[0, "severity"] == "CRITICAL"
    assert result.loc[0, "recommended_queue"] == "Payment Operations"
    assert result.loc[1, "severity"] == "HIGH"
    assert result.loc[2, "severity"] == "CRITICAL"
    assert result.loc[2, "recommended_queue"] == "Fraud Analyst"
    assert "REPEATED_EXCEPTIONS_ON_CARD" in reason_codes_for_case(result.loc[0])


def test_published_gold_loads_without_prohibited_fields():
    if not Path(DEFAULT_GOLD_PATH).exists():
        return

    gold = load_gold_data()
    prohibited = {"card_number", "cvv", "pin", "address", "latitude", "longitude"}

    assert len(gold) == 211_393
    assert gold["exception_id"].is_unique
    assert not (prohibited & set(gold.columns))
    assert set(gold["severity"].dropna().unique()) <= {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }
