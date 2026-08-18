"""Top-1/top-3 retrieval accuracy: for every known error code, the retrieved
policy_id must be the one golden-mapped to its canonical exception_type."""

import pytest

from agent.mdm import CANONICAL_EXCEPTION_TYPES, build_golden_policy_profile
from agent.retrieval import retrieve_resolution_policy

RAW_ERROR_CODES_BY_TYPE = {
    "INSUFFICIENT_BALANCE": "Insufficient Balance",
    "BAD_PIN": "Bad PIN",
    "TECHNICAL_GLITCH": "Technical Glitch",
    "BAD_CARD_NUMBER": "Bad Card Number",
    "BAD_EXPIRATION": "Bad Expiration",
    "BAD_CVV": "Bad CVV",
    "BAD_ZIPCODE": "Bad Zipcode",
}


@pytest.mark.parametrize("exception_type", CANONICAL_EXCEPTION_TYPES)
def test_top1_retrieval_matches_golden_policy(exception_type, vector_validation):
    golden_profile = build_golden_policy_profile()
    expected_policy_id = golden_profile[exception_type].policy_id

    raw_code = RAW_ERROR_CODES_BY_TYPE[exception_type]
    result = retrieve_resolution_policy(raw_code)

    assert result.top_hit is not None
    assert result.policy_id == expected_policy_id
    assert result.top_hit.policy_id == expected_policy_id


@pytest.mark.parametrize("exception_type", CANONICAL_EXCEPTION_TYPES)
def test_top3_retrieval_contains_only_the_golden_policy(exception_type, vector_validation):
    raw_code = RAW_ERROR_CODES_BY_TYPE[exception_type]
    result = retrieve_resolution_policy(raw_code, top_k=3)
    policy_ids_returned = {hit.policy_id for hit in result.hits}
    assert policy_ids_returned == {result.policy_id}


def test_unknown_error_code_returns_no_hits_and_a_limitation():
    result = retrieve_resolution_policy("Not A Real Error Code")
    assert result.hits == []
    assert result.limitations
