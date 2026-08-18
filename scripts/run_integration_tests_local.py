"""Run integration tests without pytest (local smoke runner)."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

mod = importlib.import_module("tests.integration.test_orchestrator")

tests = [
    mod.test_orchestrator_allow_path,
    mod.test_orchestrator_kill_switch_blocks,
    mod.test_orchestrator_require_approval,
    mod.test_orchestrator_deny_fraud,
]

def main():
    failures = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            print(f"[PASS] {name}")
        except AssertionError as e:
            failures += 1
            print(f"[FAIL] {name}: {e}")
        except Exception as e:
            failures += 1
            print(f"[ERROR] {name}: {e}")
    if failures:
        print(f"{failures} test(s) failed")
        raise SystemExit(1)
    print("All integration tests passed")

if __name__ == "__main__":
    main()
