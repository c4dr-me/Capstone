from agent_v2.api import investigate_exception


def test_investigate_exception_returns_proposal_only():
    result = investigate_exception({"exception_id":"EXC-1","transaction_id":"TX-1","exception_type":"TECHNICAL_GLITCH","amount":1.0,"fraud_label":"No","risk":"LOW","severity":"HIGH","masked_card_id":"card_hash","retry_count":0,"status":"NEW","high_value":False,"queue":"OPERATIONS"})
    assert result.action == "SIMULATE_RETRY_PAYMENT"
    assert result.intent == "ACT"