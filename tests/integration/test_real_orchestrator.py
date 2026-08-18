"""Real governed-orchestrator coverage for the service-container CI lane."""

from integration.orchestrator import process_event
from tests.agent.conftest import first_exception_id_for


def test_real_orchestrator_processes_a_gold_case_with_governance(gold_df):
    exception_id = first_exception_id_for(gold_df, "Technical Glitch")

    result = process_event(
        {
            "exception_id": exception_id,
            "trace_id": f"TRACE-CI-{exception_id}",
            "requester_user_id": "ops_01",
        }
    )

    assert result["exception_id"] == exception_id
    assert result["status"] != "AGENT_BLOCKED"
    assert result["proposal"]["policy_id"] == "POL-TECH-001"
    assert result["authorization"]["authorization_id"]
    assert result["receipt"]["receipt_id"]