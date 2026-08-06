"""Tests the MDM-in-RAG layer: entity resolution, golden record, survivorship."""

import pytest

from agent.mdm import (
    CANONICAL_EXCEPTION_TYPES,
    GoldenPolicyRecord,
    build_golden_policy_profile,
    golden_chunks_for,
    resolve_exception_type,
)
from agent.policy_library import PolicyChunk, load_policy_library


def test_all_seven_canonical_exception_types_present():
    assert len(CANONICAL_EXCEPTION_TYPES) == 7


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Technical Glitch", "TECHNICAL_GLITCH"),
        ("technical_glitch", "TECHNICAL_GLITCH"),
        ("tech glitch", "TECHNICAL_GLITCH"),
        ("Bad PIN", "BAD_PIN"),
        ("BAD CVV", "BAD_CVV"),
        ("Insufficient Balance", "INSUFFICIENT_BALANCE"),
    ],
)
def test_entity_resolution_normalizes_known_aliases(raw, expected):
    assert resolve_exception_type(raw) == expected


def test_entity_resolution_returns_none_for_unknown_code():
    assert resolve_exception_type("Something Unheard Of") is None


def test_golden_profile_has_one_record_per_canonical_type():
    profile = build_golden_policy_profile()
    assert set(profile) == set(CANONICAL_EXCEPTION_TYPES)
    for exception_type, record in profile.items():
        assert isinstance(record, GoldenPolicyRecord)
        assert record.exception_type == exception_type
        assert record.chunk_ids


def test_golden_profile_missing_type_raises():
    real_chunks = load_policy_library()
    partial_chunks = [c for c in real_chunks if c.exception_type != "BAD_ZIPCODE"]
    with pytest.raises(ValueError, match="BAD_ZIPCODE"):
        build_golden_policy_profile(partial_chunks)


def _make_chunk(exception_type: str, policy_id: str, version: str, source_file: str) -> PolicyChunk:
    return PolicyChunk(
        policy_id=policy_id,
        policy_title=f"{policy_id} title",
        exception_type=exception_type,
        version=version,
        responsible_team="Test Team",
        default_severity="LOW",
        recommended_queue="Test Queue",
        human_approval_required=False,
        sla_hours=24,
        section_title="Recommended Action",
        anchor="recommended-action",
        text=f"do the {policy_id} thing",
        source_file=source_file,
    )


def test_survivorship_rule_prefers_highest_version():
    old = _make_chunk("BAD_PIN", "POL-PIN-001", "1.0", "bad_pin.md")
    new = _make_chunk("BAD_PIN", "POL-PIN-001", "2.0", "bad_pin.md")
    real_chunks = [c for c in load_policy_library() if c.exception_type != "BAD_PIN"]

    profile = build_golden_policy_profile(real_chunks + [old, new])
    record = profile["BAD_PIN"]
    assert record.version == "2.0"
    assert "CONFLICT" not in record.survivorship_note

    kept = golden_chunks_for("BAD_PIN", real_chunks + [old, new])
    assert all(c.version == "2.0" for c in kept)
    assert old.chunk_id not in {c.chunk_id for c in kept}


def test_survivorship_conflict_between_two_policy_ids_is_flagged_not_silent():
    duplicate_a = _make_chunk("BAD_PIN", "POL-PIN-001", "1.0", "bad_pin.md")
    duplicate_b = _make_chunk("BAD_PIN", "POL-PIN-ALT", "1.0", "bad_pin_alt.md")
    real_chunks = [c for c in load_policy_library() if c.exception_type != "BAD_PIN"]

    profile = build_golden_policy_profile(real_chunks + [duplicate_a, duplicate_b])
    record = profile["BAD_PIN"]
    assert "CONFLICT" in record.survivorship_note


def test_golden_chunks_for_unknown_type_returns_empty():
    assert golden_chunks_for("NOT_A_REAL_TYPE") == []
