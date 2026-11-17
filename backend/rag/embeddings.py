"""Compatibility embeddings for the existing 384-dimensional Chroma collection."""

from typing import List


EMBEDDING_DIMENSION = 384
EMBEDDING_MODEL = "legacy-zero-vector-384"


def embed_texts(texts: List[str]) -> list[list[float]]:
    return [[0.0] * EMBEDDING_DIMENSION for _ in texts]
