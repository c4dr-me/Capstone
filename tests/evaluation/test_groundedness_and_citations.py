"""Citation completeness and groundedness: every recommendation must cite at
least one real policy section, and the cited text must actually support the
recommended action (a crude but concrete groundedness check: the recommended
action's key verb/object phrase appears in the cited chunk text).
"""

from agent.orchestrator import investigate_exception
from agent.policy_library import load_policy_library
from tests.agent.conftest import first_exception_id_for

ALL_ERROR_TYPES = [
    "Insufficient Balance",
    "Bad PIN",
    "Technical Glitch",
    "Bad Card Number",
    "Bad Expiration",
    "Bad CVV",
    "Bad Zipcode",
]


def test_every_error_type_produces_at_least_one_citation(gold_df):
    for error_type in ALL_ERROR_TYPES:
        exception_id = first_exception_id_for(gold_df, error_type)
        result = investigate_exception(exception_id)
        assert not result["blocked"], (error_type, result)
        assert len(result["citations"]) >= 1, error_type


def test_every_citation_resolves_to_a_real_policy_chunk(gold_df):
    all_chunks = load_policy_library()
    known_citations = {c.citation for c in all_chunks}

    for error_type in ALL_ERROR_TYPES:
        exception_id = first_exception_id_for(gold_df, error_type)
        result = investigate_exception(exception_id)
        for citation in result["citations"]:
            assert citation in known_citations, f"unknown citation: {citation}"


def test_recommended_action_is_grounded_in_the_recommended_action_chunk(gold_df):
    all_chunks = load_policy_library()
    chunk_by_citation = {c.citation: c for c in all_chunks}

    for error_type in ALL_ERROR_TYPES:
        exception_id = first_exception_id_for(gold_df, error_type)
        result = investigate_exception(exception_id)

        action_citations = [c for c in result["citations"] if c.endswith("#recommended-action")]
        assert action_citations, f"no recommended-action citation for {error_type}"

        chunk = chunk_by_citation[action_citations[0]]
        normalized_chunk_text = " ".join(chunk.text.split())
        assert result["recommended_action"] in normalized_chunk_text or normalized_chunk_text.startswith(
            result["recommended_action"][:40]
        )
