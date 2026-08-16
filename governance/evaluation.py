"""Measured Member 1 acceptance scenarios and optional Neo4j latency probe."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
from typing import Any

from contracts import Action, AuthenticatedSession, AuthorizationRequest
from governance.fakes import FakeGovernanceAdapter


@dataclass(frozen=True)
class Scenario:
    name: str
    user_id: str
    exception_id: str
    action: Action
    exception_type: str
    amount: float
    fraud_label: str
    expected: str


SCENARIOS = (
    Scenario("low risk sandbox", "ops_01", "EXC-DEMO-LOW", Action.SIMULATE_RETRY_PAYMENT, "Technical Glitch", 120, "No", "ALLOW"),
    Scenario("unknown fraud sandbox", "ops_01", "EXC-DEMO-UNKNOWN", Action.SIMULATE_RETRY_PAYMENT, "Technical Glitch", 120, "Unknown", "REQUIRE_APPROVAL"),
    Scenario("high value sandbox", "ops_01", "EXC-DEMO-HIGH", Action.SIMULATE_RETRY_PAYMENT, "Technical Glitch", 425.5, "No", "REQUIRE_APPROVAL"),
    Scenario("fraud positive sandbox", "manager_01", "EXC-DEMO-FRAUD", Action.SIMULATE_RETRY_PAYMENT, "Technical Glitch", 80, "Yes", "DENY"),
    Scenario("auditor escalation", "auditor_01", "EXC-DEMO-LOW", Action.ESCALATE, "Technical Glitch", 120, "No", "DENY"),
    Scenario("agent live retry", "resolveone_agent", "EXC-DEMO-LOW", Action.RETRY_PAYMENT, "Technical Glitch", 120, "No", "DENY"),
    Scenario("operations live retry", "ops_01", "EXC-DEMO-LOW", Action.RETRY_PAYMENT, "Technical Glitch", 120, "No", "REQUIRE_APPROVAL"),
    Scenario("authorized escalation", "ops_01", "EXC-DEMO-LOW", Action.ESCALATE, "Technical Glitch", 120, "No", "ALLOW"),
    Scenario("unsupported refund", "manager_01", "EXC-DEMO-LOW", Action.REFUND_PAYMENT, "Technical Glitch", 120, "No", "DENY"),
)


def _percent(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 2) if denominator else 0.0


def measure_scenarios() -> dict[str, Any]:
    adapter = FakeGovernanceAdapter()
    results = []
    complete_receipts = 0
    complete_lineages = 0
    unauthorized_bypasses = 0
    correct = 0
    manager = adapter.mint_access_context(AuthenticatedSession(user_id="manager_01"))
    for index, scenario in enumerate(SCENARIOS, start=1):
        context = adapter.mint_access_context(AuthenticatedSession(user_id=scenario.user_id))
        request = AuthorizationRequest(
            request_id=f"REQ-EVAL-{index:03d}",
            access_context_id=context.context_id,
            agent_id="recovery_agent",
            exception_id=scenario.exception_id,
            action=scenario.action,
            policy_id="POL-TECH-001",
            asserted_case_context={
                "exception_type": scenario.exception_type,
                "amount": scenario.amount,
                "fraud_label": scenario.fraud_label,
            },
        )
        response = adapter.authorize_action(request, context)
        is_correct = response.decision == scenario.expected
        correct += int(is_correct)
        unauthorized_bypasses += int(scenario.expected != "ALLOW" and response.decision == "ALLOW")
        receipt = adapter.get_governance_receipt(response.receipt_id, manager)
        complete_receipts += int(
            bool(receipt.integrity_hash)
            and bool(receipt.revisions)
            and receipt.authorization_id == response.authorization_id
        )
        lineage = adapter.get_case_lineage(scenario.exception_id, manager)
        complete_lineages += int(lineage.completeness == 1.0)
        results.append(
            {
                "scenario": scenario.name,
                "expected": scenario.expected,
                "actual": response.decision,
                "correct": is_correct,
                "receipt_id": response.receipt_id,
                "lineage_completeness": lineage.completeness,
            }
        )
    count = len(SCENARIOS)
    return {
        "authorization_scenario_count": count,
        "authorization_accuracy_percent": _percent(correct, count),
        "unauthorized_bypass_count": unauthorized_bypasses,
        "receipt_completeness_percent": _percent(complete_receipts, count),
        "lineage_completeness_percent": _percent(complete_lineages, count),
        "scenario_results": results,
    }


def measure_governance_tests(repo_root: Path) -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/governance", "-q"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    combined = f"{process.stdout}\n{process.stderr}"
    passed = int(match.group(1)) if (match := re.search(r"(\d+) passed", combined)) else 0
    failed = int(match.group(1)) if (match := re.search(r"(\d+) failed", combined)) else 0
    total = passed + failed
    return {
        "governance_tests_passed": passed,
        "governance_tests_failed": failed,
        "governance_tests_passing_percent": _percent(passed, total),
        "pytest_exit_code": process.returncode,
    }


def _nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999999) - 1))
    return round(ordered[index], 3)


def measure_neo4j_latency() -> dict[str, Any]:
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        return {
            "neo4j_connected": False,
            "neo4j_query_count": 0,
            "neo4j_query_p50_ms": None,
            "neo4j_query_p95_ms": None,
            "neo4j_unavailable_reason": "NEO4J_PASSWORD is not configured",
        }
    from trust_graph.neo4j_client import Neo4jClient

    client = Neo4jClient(
        os.environ.get("NEO4J_URI", "neo4j://localhost:7687"),
        os.environ.get("NEO4J_USER", "neo4j"),
        password,
        os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
    try:
        client.verify_connectivity()
        samples = []
        for sample in range(20):
            started = perf_counter()
            client.execute("RETURN $sample AS sample", {"sample": sample})
            samples.append((perf_counter() - started) * 1000)
        return {
            "neo4j_connected": True,
            "neo4j_query_count": len(samples),
            "neo4j_query_p50_ms": _nearest_rank(samples, 0.50),
            "neo4j_query_p95_ms": _nearest_rank(samples, 0.95),
            "neo4j_unavailable_reason": None,
        }
    except Exception as exc:
        return {
            "neo4j_connected": False,
            "neo4j_query_count": 0,
            "neo4j_query_p50_ms": None,
            "neo4j_query_p95_ms": None,
            "neo4j_unavailable_reason": f"{type(exc).__name__}: {exc}",
        }
    finally:
        client.close()


def build_report(repo_root: Path) -> dict[str, Any]:
    return {
        "report_version": "member1-governance-v1",
        "metrics_hard_coded": False,
        "measurement_method": "deterministic scenario execution, receipt/lineage reads, pytest subprocess, and optional live Neo4j probes",
        **measure_scenarios(),
        **measure_governance_tests(repo_root),
        **measure_neo4j_latency(),
    }
