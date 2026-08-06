from agent.orchestrator import investigate_exception
from tests.agent.conftest import first_exception_id_for

RESPONSE_KEYS = {
    "exception_id",
    "severity",
    "recommended_queue",
    "recommended_action",
    "reason_codes",
    "policy_id",
    "policy_version",
    "citations",
    "confidence",
    "approval_required",
    "evidence_record_ids",
    "limitations",
}


def test_investigate_exception_returns_documented_schema(gold_df):
    exception_id = first_exception_id_for(gold_df, "Technical Glitch")
    result = investigate_exception(exception_id)
    assert RESPONSE_KEYS.issubset(result.keys())
    assert result["exception_id"] == exception_id
    assert result["blocked"] is False


def test_investigate_exception_technical_glitch_vertical_slice(gold_df):
    exception_id = first_exception_id_for(gold_df, "Technical Glitch")
    result = investigate_exception(exception_id)

    assert result["policy_id"] == "POL-TECH-001"
    assert any(c.startswith("technical_glitch.md#") for c in result["citations"])
    assert result["approval_required"] is True
    assert result["evidence_record_ids"] == [f"TXN-{gold_df[gold_df['exception_id'] == exception_id].iloc[0]['transaction_id']}"]
    assert 0.0 <= result["confidence"] <= 1.0


def test_investigate_exception_unknown_id_is_blocked():
    result = investigate_exception("EXC-DOES-NOT-EXIST")
    assert result["blocked"] is True
    assert result["block_reason"] == "contract_validation_failed"
    assert result["recommended_action"] is None


def test_investigate_exception_every_case_has_at_least_one_citation(gold_df):
    sample_ids = gold_df["exception_id"].sample(n=10, random_state=7).tolist()
    for exception_id in sample_ids:
        result = investigate_exception(exception_id)
        assert not result["blocked"], result
        assert len(result["citations"]) >= 1
