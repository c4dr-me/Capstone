from agent.routing import RECOMMENDED_QUEUE_BY_TYPE, calculate_recommended_queue


def test_all_seven_error_types_have_a_queue():
    expected = {
        "INSUFFICIENT_BALANCE",
        "BAD_PIN",
        "TECHNICAL_GLITCH",
        "BAD_CARD_NUMBER",
        "BAD_EXPIRATION",
        "BAD_CVV",
        "BAD_ZIPCODE",
    }
    assert set(RECOMMENDED_QUEUE_BY_TYPE) == expected


def test_queue_matches_implementation_table():
    assert RECOMMENDED_QUEUE_BY_TYPE["INSUFFICIENT_BALANCE"] == "Customer Payment Support"
    assert RECOMMENDED_QUEUE_BY_TYPE["BAD_PIN"] == "Card Support"
    assert RECOMMENDED_QUEUE_BY_TYPE["TECHNICAL_GLITCH"] == "Payment Operations"
    assert RECOMMENDED_QUEUE_BY_TYPE["BAD_CARD_NUMBER"] == "Payment Validation"
    assert RECOMMENDED_QUEUE_BY_TYPE["BAD_EXPIRATION"] == "Card Support"
    assert RECOMMENDED_QUEUE_BY_TYPE["BAD_CVV"] == "Card Security Review"
    assert RECOMMENDED_QUEUE_BY_TYPE["BAD_ZIPCODE"] == "Payment Validation"


def test_fraud_context_routes_to_fraud_analyst(gold_df):
    fraud_rows = gold_df[gold_df["fraud_label"] == "Yes"]
    exception_id = fraud_rows.iloc[0]["exception_id"]
    queue, severity_result = calculate_recommended_queue(exception_id)
    assert queue == "Fraud Analyst"
    assert severity_result.final_severity == "CRITICAL"


def test_non_fraud_case_routes_to_type_queue(gold_df):
    non_fraud_rows = gold_df[
        (gold_df["error_types"] == "Bad CVV") & (gold_df["fraud_label"] != "Yes")
    ]
    assert not non_fraud_rows.empty
    exception_id = non_fraud_rows.iloc[0]["exception_id"]
    queue, severity_result = calculate_recommended_queue(exception_id)
    assert queue == "Card Security Review"
