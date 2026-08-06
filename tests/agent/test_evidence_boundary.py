"""Enforces that agent code never reads from data/raw/.

Member 2 must read only Member 1's published Gold data (implementation_team_split.md,
"Input contract" for Member 2). This test statically scans every module under
agent/ for any *code* reference (string literal, not comment/docstring prose)
to the raw data directory or its known filenames.
"""

import ast
from pathlib import Path

from agent.config import RAW_DATA_DIR, REPO_ROOT

AGENT_DIR = REPO_ROOT / "agent"
RAW_FILENAMES = {
    "transactions_data.csv",
    "cards_data.csv",
    "mcc_codes.json",
    "train_fraud_labels.json",
    "users_data.csv",
}


def _string_literals(path: Path) -> set[str]:
    """All string literals used as *code* (arguments, defaults, etc.),
    excluding module/class/function docstrings — prose explaining the
    boundary should not itself trip the boundary check.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)

    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value not in docstrings
    }


def test_raw_data_dir_is_never_referenced_in_agent_code():
    offending = []
    for path in AGENT_DIR.rglob("*.py"):
        for literal in _string_literals(path):
            if "data/raw" in literal or "data\\raw" in literal:
                offending.append(f"{path}: string literal references data/raw: {literal!r}")
            for filename in RAW_FILENAMES:
                if filename in literal:
                    offending.append(f"{path}: string literal references raw filename '{filename}'")
    assert not offending, f"agent/ code references raw data sources: {offending}"


def test_raw_data_dir_exists_but_is_untouched_by_evidence_module():
    assert RAW_DATA_DIR.exists(), "expected data/raw/ to exist for this check to be meaningful"

    import agent.evidence as evidence_module

    literals = _string_literals(Path(evidence_module.__file__))
    assert not any(f in literal for literal in literals for f in RAW_FILENAMES)
    assert not any("data/raw" in literal for literal in literals)
