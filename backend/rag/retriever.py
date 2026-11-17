"""Knowledge Base retriever module for ResolveX RAG.

Provides semantic and keyword-based document retrieval with metadata filters,
returning cited chunks: [{"doc": ..., "chunk": ..., "score": ...}].
"""

import os
import pathlib
import time
from typing import Any, Dict, List, Optional
import chromadb

from .embeddings import EMBEDDING_MODEL, embed_texts
from .documents import SUPPORTED_EXTENSIONS, chunk_text, load_document

DOCUMENTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "documents"

def retrieve_knowledge(
    query: str,
    category: Optional[str] = None,
    top_k: int = 3,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-k relevant chunks for a user query and optional category filter."""
    started = time.perf_counter()
    results = []
    method = "chroma"
    warning = None
    
    # 1. Attempt Chroma retrieval if collection exists
    try:
        persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        client = chromadb.PersistentClient(path=persist_directory)
        coll = client.get_collection(name="resolvex_docs")
        where_filter = {"category": category} if category else None
        collection_size = coll.count()
        if collection_size == 0:
            method = "keyword_fallback"
        else:
            query_kwargs = {
                "query_embeddings": embed_texts([query]),
                "n_results": min(top_k, collection_size),
            }
            if where_filter:
                query_kwargs["where"] = where_filter
            c_res = coll.query(**query_kwargs)
            if c_res and c_res.get("documents") and c_res["documents"][0]:
                docs = c_res["documents"][0]
                metas = c_res["metadatas"][0]
                for doc_text, meta in zip(docs, metas):
                    title = meta.get("title", meta.get("doc_id", "Runbook"))
                    chunk_index = meta.get("chunk_idx")
                    results.append({
                        "doc": title,
                        "category": meta.get("category", "general"),
                        "source_path": meta.get("source_path", ""),
                        "doc_id": meta.get("doc_id"),
                        "chunk_idx": chunk_index,
                        "citation": (
                            f"{title}#chunk-{chunk_index}"
                            if chunk_index is not None
                            else str(title)
                        ),
                        "chunk": doc_text,
                        "score": None,
                        "score_method": None,
                    })
            if not results:
                method = "keyword_fallback"
    except Exception as exc:
        method = "keyword_fallback"
        warning = type(exc).__name__

    # 2. Text-based semantic fallback against local document files in ./documents
    if not results and method == "keyword_fallback" and DOCUMENTS_DIR.exists():
        tokens = set(query.lower().split())
        doc_candidates = []
        for file_path in DOCUMENTS_DIR.rglob("*"):
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            text = load_document(file_path)
            file_category = file_path.parent.name if file_path.parent != DOCUMENTS_DIR else "general"
            
            for chunk_index, para in enumerate(chunk_text(text)):
                para_lower = para.lower()
                matches = sum(1 for token in tokens if token in para_lower)
                # Boost if category matches
                if category and category.lower() in file_path.stem.lower():
                    matches += 2
                if matches > 0:
                    doc_candidates.append({
                        "doc": file_path.stem.replace("_", " ").title(),
                        "category": file_category,
                        "source_path": str(file_path),
                        "doc_id": str(file_path.resolve()),
                        "chunk_idx": chunk_index,
                        "citation": f"{file_path.stem.replace('_', ' ').title()}#chunk-{chunk_index}",
                        "chunk": para,
                        "score": round(min(matches / max(len(tokens), 1), 0.99), 3),
                        "score_method": "lexical_overlap",
                    })
        doc_candidates.sort(key=lambda x: x["score"], reverse=True)
        results = doc_candidates[:top_k]

    if diagnostics is not None:
        diagnostics.update({
            "method": method,
            "status": "success" if results else "no_results",
            "warning": warning,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "result_count": len(results),
            "embedding_model": EMBEDDING_MODEL if method == "chroma" else None,
            "relevance_scores_available": method != "chroma",
        })

    return results
