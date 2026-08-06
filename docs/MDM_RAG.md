# MDM Applied to RAG: the Golden Policy Profile

## Why this exists

`implementation_team_split.md` gives Member 1 ownership of MDM for
customer/card master data (`golden_payment_profile`). That MDM discipline —
entity resolution, a single golden record, an explicit survivorship rule, and
a stewardship/approval flag — is exactly the discipline a policy-retrieval
RAG system needs too, applied to a different kind of master data: the
*policy documents themselves*. Without it, retrieval quality depends on the
caller supplying an exact, canonical error-code string, and nothing stops two
conflicting policy revisions from both being searchable at once.

[`agent/mdm.py`](../agent/mdm.py) implements this layer. It sits between the
raw Gold `error_types` string and the pgvector similarity search in
[`agent/vector_store.py`](../agent/vector_store.py).

## The four MDM concepts, applied to policies

### 1. Entity resolution

`resolve_exception_type(raw_error_code)` normalizes any observed spelling —
`"Technical Glitch"`, `"technical_glitch"`, `"tech glitch"` — to one of seven
canonical `exception_type` keys (`_ALIAS_MAP` in `agent/mdm.py`). Multi-error
Gold rows (`"Bad PIN,Insufficient Balance"`) are split on `,` by the caller
(`agent/severity.py`) before this resolution step, so every component error
resolves independently.

### 2. Golden record

`build_golden_policy_profile()` builds one `GoldenPolicyRecord` per canonical
exception type — the single approved `(policy_id, version)` pointer that
downstream retrieval, severity, and routing all read from. This is the direct
analogue of Member 1's `golden_payment_profile`: one masked card ID → one
approved profile; here, one canonical exception type → one approved policy
version.

### 3. Survivorship rule

When multiple policy chunks declare the same `exception_type` (e.g. a stale
duplicate of a policy document, or a genuine revision), the rule is explicit
and testable, not implicit:

- **Same `policy_id`, different `version`**: the highest version wins. The
  older version's chunks are excluded from the golden set entirely —
  `golden_chunks_for()` only returns chunks belonging to the winning version.
- **Different `policy_id`s claiming the same `exception_type` at the same
  version**: this is a genuine conflict, not something to silently pick a
  winner for. `survivorship_note` is set to a `CONFLICT: ...` string
  identifying every colliding `policy_id`, and `retrieve_resolution_policy()`
  surfaces that string in its `limitations` list rather than hiding it. This
  mirrors the project's fail-closed-and-explain governance posture (compare
  the reference course material's "AI must not silently change contracts,
  policies or golden records" note in `day3-governance-catalog-mdm.md`).

See
[`tests/agent/test_mdm_rag.py`](../tests/agent/test_mdm_rag.py)'s
`test_survivorship_rule_prefers_highest_version` and
`test_survivorship_conflict_between_two_policy_ids_is_flagged_not_silent`.

### 4. Stewardship / approval gate

Each golden record carries its policy's own `human_approval_required` flag.
`agent/graph.py`'s `generate_recommendation` node reads this flag directly
from the golden record (not from a caller-supplied argument), so an agent
cannot silently attach an unapproved policy's guidance to a recommendation
and skip the approval step — the golden record is the only source of truth
for whether a policy requires human sign-off.

## Retrieval is golden-record-scoped, not free-text

`retrieve_resolution_policy()` in [`agent/retrieval.py`](../agent/retrieval.py)
does not run an unrestricted vector search. It first resolves the raw error
code to a canonical `exception_type`, looks up that type's golden record, and
then restricts the pgvector similarity search
(`similarity_search(..., exception_type=exception_type, ...)`) to only that
type's chunks. This means the vector index in Postgres can physically contain
stale or conflicting chunks (useful for testing survivorship handling) without
ever being able to leak one into a live recommendation — the MDM boundary is
enforced at the query filter, not just at index-build time.

## Evaluation

[`tests/evaluation/test_retrieval_accuracy.py`](../tests/evaluation/test_retrieval_accuracy.py)
verifies that for all seven canonical exception types, top-1 and top-3
retrieval return only the golden policy's chunks — measured at 100% in
[`agent_evaluation_results.json`](agent_evaluation_results.json).
