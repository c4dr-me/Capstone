from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integration.orchestrator import process_event
from execution.kill_switch import KillSwitch


def test_orchestrator_allow_path():
    event = {"exception_id": "EXC-101", "case": {"exception_id": "EXC-101", "exception_type": "Technical Glitch", "fraud_label": "No", "amount": 120.0}}
    out = process_event(event)
    assert out["status"] in {"SUCCESS", "FAILED"}
    assert out["authorization"]["decision"] == "ALLOW"


def test_orchestrator_kill_switch_blocks():
    ks = KillSwitch()
    ks.set_enabled(False)
    event = {"exception_id": "EXC-102", "case": {"exception_id": "EXC-102", "exception_type": "Technical Glitch", "fraud_label": "No", "amount": 50.0}}
    out = process_event(event)
    assert out["status"] == "ALLOW_AUTONOMY_DISABLED"
    ks.set_enabled(True)


def test_orchestrator_require_approval():
    event = {"exception_id": "EXC-103", "case": {"exception_id": "EXC-103", "exception_type": "Technical Glitch", "fraud_label": "No", "amount": 20000.0}}
    out = process_event(event)
    assert out["status"] == "PENDING_APPROVAL"


def test_orchestrator_deny_fraud():
    event = {"exception_id": "EXC-104", "case": {"exception_id": "EXC-104", "exception_type": "Technical Glitch", "fraud_label": "Yes", "amount": 100.0}}
    out = process_event(event)
    assert out["status"] == "DENIED"
