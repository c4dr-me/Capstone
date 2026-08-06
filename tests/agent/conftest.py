import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def first_exception_id_for(gold_df, error_type: str) -> str:
    matches = gold_df[gold_df["error_types"] == error_type]
    assert not matches.empty, f"no Gold case found for error_types == '{error_type}'"
    return matches.iloc[0]["exception_id"]
