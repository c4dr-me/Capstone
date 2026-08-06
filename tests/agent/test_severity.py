import pandas as pd
import pytest

from agent.config import HIGH_VALUE_AMOUNT_THRESHOLD, REPEATED_EXCEPTIONS_THRESHOLD
from agent.severity import BASE_SEVERITY_BY_TYPE, calculate_exception_severity
from tests.agent.conftest import first_exception_id_for


def test_all_seven_error_types_have_a_base_severity():
    expected = {
        "INSUFFICIENT_BALANCE",
        "BAD_PIN",
        "TECHNICAL_GLITCH",
        "BAD_CARD_NUMBER",
        "BAD_EXPIRATION",
        "BAD_CVV",
        "BAD_ZIPCODE",
    }
    assert set(BASE_SEVERITY_BY_TYPE) == expected


def test_base_severity_matches_implementation_table():
    assert BASE_SEVERITY_BY_TYPE["INSUFFICIENT_BALANCE"] == "LOW"
    assert BASE_SEVERITY_BY_TYPE["BAD_PIN"] == "MEDIUM"
    assert BASE_SEVERITY_BY_TYPE["TECHNICAL_GLITCH"] == "HIGH"
    assert BASE_SEVERITY_BY_TYPE["BAD_CARD_NUMBER"] == "MEDIUM"
    assert BASE_SEVERITY_BY_TYPE["BAD_EXPIRATION"] == "MEDIUM"
    assert BASE_SEVERITY_BY_TYPE["BAD_CVV"] == "HIGH"
    assert BASE_SEVERITY_BY_TYPE["BAD_ZIPCODE"] == "LOW"


def test_unknown_exception_id_raises(gold_df):
    with pytest.raises(ValueError):
        calculate_exception_severity("EXC-DOES-NOT-EXIST")


def test_severity_never_exceeds_critical(gold_df):
    sample_ids = gold_df["exception_id"].sample(n=50, random_state=42).tolist()
    for exception_id in sample_ids:
        result = calculate_exception_severity(exception_id)
        assert result.final_severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_fraud_context_forces_critical(gold_df):
    fraud_rows = gold_df[gold_df["fraud_label"] == "Yes"]
    assert not fraud_rows.empty
    exception_id = fraud_rows.iloc[0]["exception_id"]
    result = calculate_exception_severity(exception_id)
    assert result.final_severity == "CRITICAL"
    assert "FRAUD_CONTEXT_PRESENT" in result.reason_codes


def test_high_value_transaction_escalates(gold_df):
    high_value_low_base = gold_df[
        (gold_df["amount"] >= HIGH_VALUE_AMOUNT_THRESHOLD)
        & (gold_df["error_types"] == "Insufficient Balance")
        & (~gold_df["is_multi_error"])
        & (gold_df["fraud_label"] != "Yes")
    ]
    assert not high_value_low_base.empty
    exception_id = high_value_low_base.iloc[0]["exception_id"]
    result = calculate_exception_severity(exception_id)
    assert result.base_severity == "LOW"
    assert "HIGH_VALUE_TRANSACTION" in result.reason_codes
    assert result.final_severity != "LOW"


def test_multi_error_case_escalates(gold_df):
    multi_error_rows = gold_df[gold_df["is_multi_error"]]
    assert not multi_error_rows.empty
    exception_id = multi_error_rows.iloc[0]["exception_id"]
    result = calculate_exception_severity(exception_id)
    assert "MULTI_ERROR_CASE" in result.reason_codes


def test_repeated_exceptions_on_card_escalates(gold_df):
    repeat_counts = gold_df.groupby("masked_card_id").size()
    repeated_card = repeat_counts[repeat_counts >= REPEATED_EXCEPTIONS_THRESHOLD].index[0]
    exception_id = gold_df[gold_df["masked_card_id"] == repeated_card].iloc[0]["exception_id"]
    result = calculate_exception_severity(exception_id)
    assert "REPEATED_EXCEPTIONS_ON_CARD" in result.reason_codes


def test_multi_error_primary_type_is_highest_severity_component(gold_df):
    multi_error_rows = gold_df[gold_df["error_types"].str.contains(",", na=False)]
    assert not multi_error_rows.empty
    for _, row in multi_error_rows.head(20).iterrows():
        result = calculate_exception_severity(row["exception_id"])
        component_base_severities = [
            BASE_SEVERITY_BY_TYPE[t] for t in result.component_exception_types
        ]
        expected_base = max(
            component_base_severities, key=lambda s: ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(s)
        )
        assert result.base_severity == expected_base
