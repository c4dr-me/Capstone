from utils.runtime_store import RuntimeStore


def test_decision_is_persisted_with_audit_event(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.db")
    recommendation = {
        "exception_id": "EXC-1",
        "recommended_action": "Review governed evidence.",
    }

    receipt = store.record_decision(
        exception_id="EXC-1",
        decision="APPROVED",
        analyst_reason="Evidence and cited policy verified.",
        recommendation=recommendation,
    )

    decisions = store.latest_decisions()
    events = store.latest_audit_events()

    assert receipt["decision"] == "APPROVED"
    assert decisions[0]["exception_id"] == "EXC-1"
    assert decisions[0]["analyst_reason"] == "Evidence and cited policy verified."
    assert events[0]["event_type"] == "RECOMMENDATION_APPROVED"
    assert store.status_by_exception() == {"EXC-1": "APPROVED"}


def test_decision_requires_reason(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.db")

    try:
        store.record_decision("EXC-1", "REJECTED", "", {})
    except ValueError as error:
        assert "analyst_reason" in str(error)
    else:
        raise AssertionError("Empty analyst reason was accepted")
