from governance.evaluation import measure_scenarios


def test_acceptance_metrics_are_computed_from_executed_scenarios():
    report = measure_scenarios()
    assert report["authorization_scenario_count"] == len(report["scenario_results"])
    assert report["authorization_accuracy_percent"] == 100.0
    assert report["unauthorized_bypass_count"] == 0
    assert report["receipt_completeness_percent"] == 100.0
    assert report["lineage_completeness_percent"] == 100.0
