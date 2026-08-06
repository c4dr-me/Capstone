"""Local TF-IDF embeddings for policy retrieval.

No network dependency or API key: a scikit-learn TfidfVectorizer is fit once
over all policy chunk text and persisted to disk. Because retrieval queries in
this system are short, controlled-vocabulary phrases (an exception type plus a
governance intent, e.g. "technical glitch controlled retry approval"), lexical
TF-IDF similarity is an accurate and fully reproducible substitute for a neural
embedding call.
"""

from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from agent.config import ARTIFACTS_DIR
from agent.policy_library import PolicyChunk

VECTORIZER_PATH = ARTIFACTS_DIR / "tfidf_vectorizer.joblib"
EMBEDDING_DIM = 512


def _chunk_text(chunk: PolicyChunk) -> str:
    return f"{chunk.exception_type} {chunk.section_title} {chunk.text}"


def fit_vectorizer(chunks: list[PolicyChunk]) -> TfidfVectorizer:
    vectorizer = TfidfVectorizer(max_features=EMBEDDING_DIM, stop_words="english")
    vectorizer.fit([_chunk_text(c) for c in chunks])
    return vectorizer


def save_vectorizer(vectorizer: TfidfVectorizer, path: Path = VECTORIZER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(vectorizer, path)


def load_vectorizer(path: Path = VECTORIZER_PATH) -> TfidfVectorizer:
    if not path.exists():
        raise FileNotFoundError(
            f"No fitted vectorizer at {path}. Run `python -m agent.build_index` first."
        )
    return joblib.load(path)


def embed_texts(vectorizer: TfidfVectorizer, texts: list[str]) -> np.ndarray:
    matrix = vectorizer.transform(texts).toarray().astype(np.float32)
    width = vectorizer.max_features or EMBEDDING_DIM
    if matrix.shape[1] < width:
        pad = np.zeros((matrix.shape[0], width - matrix.shape[1]), dtype=np.float32)
        matrix = np.hstack([matrix, pad])
    return matrix


def embed_chunks(vectorizer: TfidfVectorizer, chunks: list[PolicyChunk]) -> np.ndarray:
    return embed_texts(vectorizer, [_chunk_text(c) for c in chunks])


def embed_query(vectorizer: TfidfVectorizer, query: str) -> np.ndarray:
    return embed_texts(vectorizer, [query])[0]
