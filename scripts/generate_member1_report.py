"""Generate reports/member1/governance_results.json from executable evidence."""

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from governance.evaluation import build_report  # noqa: E402


def main() -> int:
    repo_root = REPO_ROOT
    report = build_report(repo_root)
    output = repo_root / "reports" / "member1" / "governance_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if report["pytest_exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
