"""Builds/rebuilds the pgvector policy index from policies/.

Run as: python -m agent.build_index
"""

from agent.embeddings import embed_chunks, fit_vectorizer, save_vectorizer
from agent.mdm import build_golden_policy_profile
from agent.policy_library import load_policy_library
from agent.vector_store import clear_table, ensure_schema, get_connection, upsert_chunks


def main() -> None:
    chunks = load_policy_library()
    print(f"Loaded {len(chunks)} policy chunks from {len({c.source_file for c in chunks})} files.")

    golden_profile = build_golden_policy_profile(chunks)
    print(f"\nGolden policy profile ({len(golden_profile)} canonical exception types):")
    for exception_type, record in sorted(golden_profile.items()):
        flag = " ⚠ " if "CONFLICT" in record.survivorship_note else "   "
        print(
            f"{flag}{exception_type:<22} -> {record.policy_id} v{record.version} "
            f"({record.source_file}, {len(record.chunk_ids)} chunks) — {record.survivorship_note}"
        )

    vectorizer = fit_vectorizer(chunks)
    save_vectorizer(vectorizer)
    embeddings = embed_chunks(vectorizer, chunks)
    print(f"\nFitted TF-IDF vectorizer with vocabulary size {len(vectorizer.vocabulary_)}.")

    conn = get_connection()
    try:
        ensure_schema(conn)
        clear_table(conn)
        upsert_chunks(conn, chunks, embeddings)
    finally:
        conn.close()

    print(f"Indexed {len(chunks)} chunks into pgvector table 'policy_chunks'.")


if __name__ == "__main__":
    main()
