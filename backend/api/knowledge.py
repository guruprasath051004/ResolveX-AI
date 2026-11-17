"""Administrator endpoints for knowledge documents and RAG operations."""

import hashlib
import pathlib
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AuditLog, RoleEnum, User
from backend.models import knowledge as knowledge_model
from backend.rag.documents import SUPPORTED_EXTENSIONS, load_document
from backend.rag.embeddings import EMBEDDING_MODEL
from backend.rag.indexing import (
    collection_snapshot,
    delete_document_vectors,
    document_chunks,
    index_document,
)
from backend.rag.retriever import retrieve_knowledge
from backend.services.observability import safe_text_summary
from .auth import require_roles


router = APIRouter(
    prefix="/admin/knowledge",
    tags=["knowledge-admin"],
    dependencies=[Depends(require_roles(RoleEnum.administrator))],
)

DOC_ROOT = pathlib.Path(__file__).resolve().parents[2] / "documents"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class RetrievalEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    category: str | None = Field(default=None, max_length=100)
    top_k: int = Field(default=5, ge=1, le=10)


def _file_hash(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _find_duplicate(
    db: Session,
    content_hash: str,
) -> knowledge_model.KnowledgeDocument | None:
    documents = db.query(knowledge_model.KnowledgeDocument).all()
    hashed_paths: dict[str, str] = {}
    for document in documents:
        if document.content_hash == content_hash:
            return document
        path = pathlib.Path(document.source_path)
        path_key = str(path.resolve())
        if not document.content_hash and path.is_file():
            path_hash = hashed_paths.get(path_key)
            if path_hash is None:
                path_hash = _file_hash(path)
                hashed_paths[path_key] = path_hash
        else:
            path_hash = None
        if path_hash == content_hash:
            document.content_hash = content_hash
            db.flush()
            return document
    return None


def _contained_document_path(filename: str) -> pathlib.Path:
    root = DOC_ROOT.resolve()
    if "\x00" in filename:
        raise HTTPException(status_code=422, detail="Document filename contains invalid characters.")
    name = pathlib.Path(filename).name
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=422, detail="A valid document filename is required.")
    path = (root / name).resolve()
    if path.parent != root:
        raise HTTPException(status_code=422, detail="Document path must remain inside the knowledge directory.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Supported document types are PDF, DOCX, TXT, and Markdown.",
        )
    return path


def _document_uuid(doc_id: str) -> UUID:
    try:
        return UUID(doc_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Document not found.") from exc


def _index_and_update(
    db: Session,
    document: knowledge_model.KnowledgeDocument,
) -> dict[str, Any]:
    document.index_status = "indexing"
    document.index_error = None
    db.commit()
    try:
        result = index_document(
            document_id=str(document.id),
            title=document.title,
            category=document.category,
            source_path=document.source_path,
            version_number=document.version_number,
        )
    except Exception as exc:
        db.rollback()
        document = (
            db.query(knowledge_model.KnowledgeDocument)
            .filter(knowledge_model.KnowledgeDocument.id == document.id)
            .first()
        )
        if document is None:
            raise RuntimeError("Knowledge document disappeared during indexing.") from exc
        document.index_status = "failed"
        document.index_error = safe_text_summary(
            f"{type(exc).__name__}: {exc}",
            1000,
        )
        db.commit()
        return {
            "status": "failed",
            "error": document.index_error,
            "chunk_count": 0,
        }
    document.index_status = "indexed"
    document.index_error = None
    document.chunk_count = result["chunk_count"]
    document.embedding_model = result["embedding_model"]
    document.indexed_at = datetime.utcnow()
    db.commit()
    return {"status": "indexed", **result}


def _audit(db: Session, user_id: int, action: str, document_id: str | None, details: str) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            table_name="knowledge_documents",
            record_id=None,
            details=safe_text_summary(
                f"document_id={document_id or 'all'}; {details}",
                1000,
            ),
        )
    )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(default="general", max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.administrator)),
):
    if not file.filename:
        raise HTTPException(status_code=422, detail="A document filename is required.")
    dest_path = _contained_document_path(file.filename)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded document is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds the 10 MB upload limit.")
    content_hash = hashlib.sha256(content).hexdigest()

    duplicate = _find_duplicate(db, content_hash)
    if duplicate is not None:
        _audit(
            db,
            current_user.id,
            "knowledge.duplicate_detected",
            str(duplicate.id),
            f"Duplicate upload rejected: {dest_path.name}",
        )
        db.commit()
        return {
            "id": str(duplicate.id),
            "title": duplicate.title,
            "category": duplicate.category,
            "duplicate": True,
            "duplicate_of": str(duplicate.id),
            "index_status": duplicate.index_status,
        }

    existing = (
        db.query(knowledge_model.KnowledgeDocument)
        .filter(knowledge_model.KnowledgeDocument.source_path == str(dest_path))
        .order_by(knowledge_model.KnowledgeDocument.created_at, knowledge_model.KnowledgeDocument.id)
        .first()
    )
    old_bytes = dest_path.read_bytes() if dest_path.is_file() else None
    old_content = None
    if existing is not None:
        try:
            old_content = load_document(dest_path)
        except Exception:
            old_content = existing.content
        previous_hash = existing.content_hash or (
            hashlib.sha256(old_bytes).hexdigest() if old_bytes is not None else content_hash
        )
        db.add(
            knowledge_model.KnowledgeDocumentVersion(
                document_id=existing.id,
                version_number=existing.version_number,
                content_hash=previous_hash,
                content=old_content,
                source_path=existing.source_path,
                doc_type=existing.doc_type,
                index_status=existing.index_status,
                chunk_count=existing.chunk_count,
                embedding_model=existing.embedding_model,
            )
        )
        existing.version_number += 1
        existing.content = None
        existing.title = dest_path.stem.replace("_", " ").title()
        existing.category = category.strip() or "general"
        existing.content_hash = content_hash
        existing.index_status = "pending"
        existing.index_error = None
        existing.chunk_count = 0
        document = existing
    else:
        document = knowledge_model.KnowledgeDocument(
            title=dest_path.stem.replace("_", " ").title(),
            category=category.strip() or "general",
            content=None,
            source_path=str(dest_path),
            file_path=str(dest_path),
            doc_type=dest_path.suffix.lower().lstrip("."),
            content_hash=content_hash,
            index_status="pending",
        )
        db.add(document)

    try:
        DOC_ROOT.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content)
        db.flush()
        _audit(
            db,
            current_user.id,
            "knowledge.uploaded",
            str(document.id),
            f"Uploaded {dest_path.name}; version {document.version_number}.",
        )
        db.commit()
    except Exception:
        db.rollback()
        if old_bytes is None:
            dest_path.unlink(missing_ok=True)
        else:
            dest_path.write_bytes(old_bytes)
        raise

    indexing = _index_and_update(db, document)
    _audit(
        db,
        current_user.id,
        "knowledge.indexed" if indexing["status"] == "indexed" else "knowledge.index_failed",
        str(document.id),
        f"Indexing status: {indexing['status']}.",
    )
    db.commit()
    return {
        "id": str(document.id),
        "title": document.title,
        "category": document.category,
        "version_number": document.version_number,
        "duplicate": False,
        "index_status": indexing["status"],
        "index_error": indexing.get("error"),
        "chunk_count": indexing["chunk_count"],
    }


@router.get("/")
def list_documents(db: Session = Depends(get_db)):
    documents = (
        db.query(knowledge_model.KnowledgeDocument)
        .order_by(knowledge_model.KnowledgeDocument.updated_at.desc())
        .all()
    )
    first_by_identity: dict[str, str] = {}
    output = []
    for document in documents:
        source_path = str(pathlib.Path(document.source_path).resolve())
        identity = document.content_hash or source_path
        duplicate_of = first_by_identity.get(identity)
        first_by_identity.setdefault(identity, str(document.id))
        output.append(
            {
                "id": str(document.id),
                "title": document.title,
                "category": document.category,
                "path": document.source_path,
                "doc_type": document.doc_type,
                "version_number": document.version_number,
                "content_hash": document.content_hash,
                "duplicate": duplicate_of is not None,
                "duplicate_of": duplicate_of,
                "index_status": document.index_status,
                "index_error": safe_text_summary(document.index_error, 1000),
                "chunk_count": document.chunk_count,
                "embedding_model": document.embedding_model,
                "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
            }
        )
    return output


@router.get("/stats")
def get_knowledge_stats(db: Session = Depends(get_db)):
    status_rows = (
        db.query(
            knowledge_model.KnowledgeDocument.index_status,
            func.count(knowledge_model.KnowledgeDocument.id),
        )
        .group_by(knowledge_model.KnowledgeDocument.index_status)
        .all()
    )
    documents = db.query(
        func.count(knowledge_model.KnowledgeDocument.id),
        func.count(func.distinct(knowledge_model.KnowledgeDocument.content_hash)),
        func.sum(knowledge_model.KnowledgeDocument.chunk_count),
    ).one()
    try:
        vector_stats = collection_snapshot()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"ChromaDB statistics unavailable ({type(exc).__name__}).",
        ) from exc
    return {
        "documents": int(documents[0] or 0),
        "unique_content_hashes": int(documents[1] or 0),
        "indexed_chunks": int(documents[2] or 0),
        "index_status": {status: count for status, count in status_rows},
        "vector_database": {
            **vector_stats,
            "collection": "resolvex_docs",
            "embedding_model": EMBEDDING_MODEL,
            "relevance_scores_available": False,
        },
    }


@router.post("/evaluate")
def evaluate_retrieval(
    payload: RetrievalEvaluationRequest,
):
    diagnostics: dict[str, Any] = {}
    chunks = retrieve_knowledge(
        query=payload.query.strip(),
        category=payload.category,
        top_k=payload.top_k,
        diagnostics=diagnostics,
    )
    results = []
    for chunk in chunks:
        source_path = pathlib.Path(chunk.get("source_path", ""))
        results.append(
            {
                "document": chunk.get("doc"),
                "category": chunk.get("category"),
                "citation": chunk.get("citation"),
                "citation_verified": bool(
                    chunk.get("citation")
                    and chunk.get("chunk_idx") is not None
                    and (source_path.is_file() or chunk.get("doc_id"))
                ),
                "chunk": chunk.get("chunk"),
                "relevance_score": chunk.get("score"),
                "score_method": chunk.get("score_method"),
            }
        )
    return {
        "query": safe_text_summary(payload.query, 4000),
        "retrieval_status": diagnostics.get("status", "unknown"),
        "retrieval_method": diagnostics.get("method"),
        "warning": diagnostics.get("warning"),
        "latency_ms": diagnostics.get("latency_ms"),
        "embedding_model": diagnostics.get("embedding_model"),
        "relevance_scores_available": diagnostics.get("relevance_scores_available", False),
        "result_count": len(results),
        "results": results,
    }


@router.get("/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    document_uuid = _document_uuid(doc_id)
    document = (
        db.query(knowledge_model.KnowledgeDocument)
        .filter(knowledge_model.KnowledgeDocument.id == document_uuid)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        content = document.content or load_document(pathlib.Path(document.source_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document source file is missing.") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Document preview failed ({type(exc).__name__}).",
        ) from exc
    return {
        "id": str(document.id),
        "title": document.title,
        "category": document.category,
        "doc_type": document.doc_type,
        "version_number": document.version_number,
        "index_status": document.index_status,
        "preview": content[:12000],
        "preview_truncated": len(content) > 12000,
        "versions": [
            {
                "version_number": version.version_number,
                "content_hash": version.content_hash,
                "index_status": version.index_status,
                "chunk_count": version.chunk_count,
                "created_at": version.created_at.isoformat() if version.created_at else None,
            }
            for version in document.versions
        ],
    }


@router.get("/{doc_id}/chunks")
def get_document_chunks(
    doc_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    document_uuid = _document_uuid(doc_id)
    document = (
        db.query(knowledge_model.KnowledgeDocument)
        .filter(knowledge_model.KnowledgeDocument.id == document_uuid)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    chunks = document_chunks(str(document.id), document.source_path, limit=limit)
    return {
        "document_id": str(document.id),
        "index_status": document.index_status,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.administrator)),
):
    document_uuid = _document_uuid(doc_id)
    document = (
        db.query(knowledge_model.KnowledgeDocument)
        .filter(knowledge_model.KnowledgeDocument.id == document_uuid)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    source_path = pathlib.Path(document.source_path).resolve()
    sibling = (
        db.query(knowledge_model.KnowledgeDocument.id)
        .filter(
            knowledge_model.KnowledgeDocument.source_path == document.source_path,
            knowledge_model.KnowledgeDocument.id != document.id,
        )
        .first()
    )
    if sibling is None:
        try:
            delete_document_vectors(str(document.id), str(source_path))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Document vectors could not be removed ({type(exc).__name__}).",
            ) from exc
        root = DOC_ROOT.resolve()
        if source_path.parent == root and source_path.is_file():
            source_path.unlink()
    _audit(db, current_user.id, "knowledge.deleted", str(document.id), document.title)
    db.delete(document)
    db.commit()
    return {"status": "deleted", "id": doc_id}


@router.post("/reindex")
def reindex(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.administrator)),
):
    documents = (
        db.query(knowledge_model.KnowledgeDocument)
        .order_by(knowledge_model.KnowledgeDocument.created_at, knowledge_model.KnowledgeDocument.id)
        .all()
    )
    grouped: dict[str, list[knowledge_model.KnowledgeDocument]] = {}
    for document in documents:
        grouped.setdefault(str(pathlib.Path(document.source_path).resolve()), []).append(document)

    indexed = 0
    failures = []
    for records in grouped.values():
        document = records[0]
        try:
            document.content_hash = _file_hash(pathlib.Path(document.source_path))
        except OSError as exc:
            document.index_status = "failed"
            document.index_error = safe_text_summary(
                f"{type(exc).__name__}: {exc}",
                1000,
            )
            document.chunk_count = 0
            db.commit()
            result = {
                "status": "failed",
                "error": document.index_error,
                "chunk_count": 0,
            }
        else:
            result = _index_and_update(db, document)
        for duplicate in records[1:]:
            duplicate.index_status = result["status"]
            duplicate.index_error = result.get("error")
            duplicate.chunk_count = result.get("chunk_count", 0)
            duplicate.embedding_model = result.get("embedding_model")
            duplicate.indexed_at = document.indexed_at
            duplicate.content_hash = document.content_hash
        db.commit()
        if result["status"] == "indexed":
            indexed += 1
        else:
            failures.append(
                {
                    "document_id": str(document.id),
                    "title": document.title,
                    "error": result.get("error"),
                }
            )

    _audit(
        db,
        current_user.id,
        "knowledge.reindexed",
        None,
        f"Reindexed {indexed} files; {len(failures)} failed.",
    )
    db.commit()
    return {
        "status": "completed" if not failures else "completed_with_errors",
        "files_indexed": indexed,
        "files_failed": len(failures),
        "failures": failures,
    }
