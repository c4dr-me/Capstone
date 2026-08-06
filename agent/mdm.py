"""Master Data Management applied to the policy library used by RAG.

Member 1 owns MDM for customer/card master data (golden_payment_profile). This
module applies the same MDM discipline — entity resolution, a golden record, an
explicit survivorship rule, and a stewardship/approval flag — to the *policy*
master data that the RAG layer retrieves from. Without this layer, retrieval
would depend on the caller supplying an exact, canonical error code; with it,
any raw error-code spelling on a Gold exception case resolves to exactly one
approved policy version.
"""

from dataclasses import dataclass

from agent.policy_library import PolicyChunk, load_policy_library

# Entity resolution: normalizes every raw error-code spelling observed in the
# Gold dataset (including comma-joined multi-error strings, handled by the
# caller splitting on "," before lookup) to one canonical exception_type key.
_ALIAS_MAP: dict[str, str] = {
    "insufficient balance": "INSUFFICIENT_BALANCE",
    "insufficient_balance": "INSUFFICIENT_BALANCE",
    "bad pin": "BAD_PIN",
    "bad_pin": "BAD_PIN",
    "technical glitch": "TECHNICAL_GLITCH",
    "technical_glitch": "TECHNICAL_GLITCH",
    "tech glitch": "TECHNICAL_GLITCH",
    "bad card number": "BAD_CARD_NUMBER",
    "bad_card_number": "BAD_CARD_NUMBER",
    "bad expiration": "BAD_EXPIRATION",
    "bad_expiration": "BAD_EXPIRATION",
    "bad cvv": "BAD_CVV",
    "bad_cvv": "BAD_CVV",
    "bad zipcode": "BAD_ZIPCODE",
    "bad_zipcode": "BAD_ZIPCODE",
}

CANONICAL_EXCEPTION_TYPES = sorted(set(_ALIAS_MAP.values()))


def resolve_exception_type(raw_error_code: str) -> str | None:
    """Entity resolution: map any known raw spelling to its canonical exception_type."""
    key = raw_error_code.strip().lower()
    return _ALIAS_MAP.get(key)


@dataclass(frozen=True)
class GoldenPolicyRecord:
    exception_type: str
    policy_id: str
    version: str
    source_file: str
    responsible_team: str
    default_severity: str
    recommended_queue: str
    human_approval_required: bool
    sla_hours: int
    chunk_ids: tuple[str, ...]
    survivorship_note: str


def _version_key(version: str) -> tuple:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def build_golden_policy_profile(
    chunks: list[PolicyChunk] | None = None,
) -> dict[str, GoldenPolicyRecord]:
    """Builds one golden record per canonical exception_type.

    Survivorship rule: when multiple policy documents (or duplicate revisions of
    the same document) declare the same exception_type, the highest declared
    `version` wins. Exact-duplicate chunk content (same content_hash) is
    deduplicated silently; a genuine version conflict is recorded in
    `survivorship_note` rather than silently discarded, per the project's
    fail-closed-and-explain governance requirement.
    """
    chunks = chunks if chunks is not None else load_policy_library()

    by_type: dict[str, list[PolicyChunk]] = {}
    for chunk in chunks:
        by_type.setdefault(chunk.exception_type, []).append(chunk)

    profile: dict[str, GoldenPolicyRecord] = {}
    for exception_type, group in by_type.items():
        best_version = max(_version_key(c.version) for c in group)
        winners = [c for c in group if _version_key(c.version) == best_version]

        winner_policy_ids = {c.policy_id for c in winners}
        note = "single approved version"
        if len(winner_policy_ids) > 1:
            note = (
                f"CONFLICT: {len(winner_policy_ids)} distinct policy_ids "
                f"({sorted(winner_policy_ids)}) declare exception_type "
                f"'{exception_type}' at the same highest version — "
                "steward review required before this golden record is trusted"
            )

        rep = winners[0]
        chunk_ids = tuple(sorted({c.chunk_id for c in winners}))
        profile[exception_type] = GoldenPolicyRecord(
            exception_type=exception_type,
            policy_id=rep.policy_id,
            version=rep.version,
            source_file=rep.source_file,
            responsible_team=rep.responsible_team,
            default_severity=rep.default_severity,
            recommended_queue=rep.recommended_queue,
            human_approval_required=rep.human_approval_required,
            sla_hours=rep.sla_hours,
            chunk_ids=chunk_ids,
            survivorship_note=note,
        )

    unresolved = set(CANONICAL_EXCEPTION_TYPES) - set(profile)
    if unresolved:
        raise ValueError(f"No approved policy found for exception types: {sorted(unresolved)}")

    return profile


def golden_chunks_for(
    exception_type: str, chunks: list[PolicyChunk] | None = None
) -> list[PolicyChunk]:
    """Returns only the chunks belonging to the golden (approved) policy version."""
    chunks = chunks if chunks is not None else load_policy_library()
    profile = build_golden_policy_profile(chunks)
    record = profile.get(exception_type)
    if record is None:
        return []
    allowed = set(record.chunk_ids)
    return [c for c in chunks if c.chunk_id in allowed]
