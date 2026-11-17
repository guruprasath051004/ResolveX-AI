"""Safe Chroma indexing helpers for the existing ResolveX collection."""

import os
from pathlib import Path
from typing import Any

import chromadb

from .documents import chunk_text, load_document
from .embeddings import EMBEDDING_MODEL, embed_texts


COLLECTION_NAME = "resolvex_docs"


def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_DIR", "./chroma_data"))


def collection_snapshot() -> dict[str, Any]:
    client = _client()
    collection_names = {
        getattr(collection, "name", collection)
        for collection in client.list_collections()
    }
    if COLLECTION_NAME not in collection_names:
        return {
            "status": "not_created",
            "chunk_count": 0,
            "document_count": 0,
            "documents": {},
            "embedding_dimensions": None,
        }
    collection = client.get_collection(name=COLLECTION_NAME)
    metadata_rows = collection.get(include=["metadatas"])
    grouped: dict[str, dict[str, Any]] = {}
    for metadata in metadata_rows.get("metadatas") or []:
        if not metadata:
            continue
        document_id = str(metadata.get("doc_id") or metadata.get("source_path") or "")
        if not document_id:
            continue
        item = grouped.setdefault(
            document_id,
            {
                "chunk_count": 0,
                "source_path": metadata.get("source_path"),
                "title": metadata.get("title"),
            },
        )
        item["chunk_count"] += 1
    return {
        "status": "ready",
        "chunk_count": int(metadata_rows.get("ids") and len(metadata_rows["ids"]) or 0),
        "document_count": len(grouped),
        "documents": grouped,
        "embedding_dimensions": 384 if grouped else None,
    }


def _existing_ids(collection: Any, document_id: str, source_path: str) -> set[str]:
    ids: set[str] = set()
    for where in ({"doc_id": document_id}, {"source_path": source_path}):
        result = collection.get(where=where, include=["metadatas"])
        ids.update(str(item) for item in result.get("ids") or [])
    return ids


def index_document(
    *,
    document_id: str,
    title: str,
    category: str,
    source_path: str,
    version_number: int,
) -> dict[str, Any]:
    path = Path(source_path).resolve(strict=True)
    raw_text = load_document(path)
    chunks = chunk_text(raw_text)
    if not chunks:
        raise ValueError("Document contains no extractable text.")

    client = _client()
    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    metadata = [
        {
            "doc_id": document_id,
            "title": title,
            "category": category,
            "chunk_idx": chunk_index,
            "source_path": str(path),
            "version_number": version_number,
        }
        for chunk_index in range(len(chunks))
    ]
    ids = [f"{document_id}:v{version_number}:{chunk_index}" for chunk_index in range(len(chunks))]
    previous_ids = _existing_ids(collection, document_id, str(path))
    collection.upsert(
        ids=ids,
        documents=chunks,
        metadatas=metadata,
        embeddings=embed_texts(chunks),
    )
    stale_ids = previous_ids.difference(ids)
    if stale_ids:
        collection.delete(ids=sorted(stale_ids))
    return {
        "chunk_count": len(chunks),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": 384,
    }


def delete_document_vectors(document_id: str, source_path: str) -> int:
    client = _client()
    collection_names = {
        getattr(collection, "name", collection)
        for collection in client.list_collections()
    }
    if COLLECTION_NAME not in collection_names:
        return 0
    collection = client.get_collection(name=COLLECTION_NAME)
    ids = _existing_ids(collection, document_id, str(Path(source_path).resolve()))
    if ids:
        collection.delete(ids=sorted(ids))
    return len(ids)


def document_chunks(document_id: str, source_path: str, limit: int = 200) -> list[dict[str, Any]]:
    client = _client()
    collection_names = {
        getattr(collection, "name", collection)
        for collection in client.list_collections()
    }
    if COLLECTION_NAME not in collection_names:
        return []
    collection = client.get_collection(name=COLLECTION_NAME)
    found: dict[str, dict[str, Any]] = {}
    for where in (
        {"doc_id": document_id},
        {"source_path": str(Path(source_path).resolve())},
    ):
        result = collection.get(where=where, include=["documents", "metadatas"])
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        for chunk_id, text, metadata in zip(ids, documents, metadatas):
            found[str(chunk_id)] = {
                "chunk_id": str(chunk_id),
                "text": text,
                "metadata": metadata or {},
            }
    return list(found.values())[:limit]
