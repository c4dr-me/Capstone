from utils.agent_adapter import build_local_policy_result


def test_local_policy_fallback_is_cited_and_transparent(gold_df):
    result = build_local_policy_result("EXC-7475516")

    assert result["exception_id"] == "EXC-7475516"
    assert result["policy_id"] == "POL-TECH-001"
    assert result["recommended_queue"] == "Payment Operations"
    assert result["approval_required"] is True
    assert result["source_mode"] == "approved_policy_fallback"
    assert any("#recommended-action" in item for item in result["citations"])
    assert result["limitations"]
