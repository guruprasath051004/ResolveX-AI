"""RAG ingestion script for ResolveX.

Usage:
    python -m backend.rag.ingest --source ./documents --collection resolvex_docs

The script walks the source directory, loads supported file types (md, txt, pdf, docx),
chunks each document, and writes compatible 384-dimensional legacy zero vectors to
Chroma. It also creates a SQLAlchemy record for each document in the
`knowledge_documents` table. These vectors do not provide semantic relevance scores.
"""

import argparse
import os
import pathlib

import chromadb

from chromadb.utils import embedding_functions
from .embeddings import embed_texts
from .documents import chunk_text, load_document

class ZeroEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __init__(self, dim: int = 384):
        self.dim = dim
    def __call__(self, inputs: list[str]):
        return [[0.0] * self.dim for _ in inputs]



from ..database import SessionLocal, engine
from ..models import knowledge as knowledge_model
from sqlalchemy.orm import sessionmaker

# Initialize DB session
Session = sessionmaker(bind=engine)

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into Chroma and DB")
    parser.add_argument("--source", required=True, help="Directory containing source docs")
    parser.add_argument("--collection", default="resolvex_docs", help="Chroma collection name")
    parser.add_argument("--skip-db", action="store_true", help="Index vectors without writing SQL document rows")
    args = parser.parse_args()

    source_dir = pathlib.Path(args.source)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory {source_dir} not found")

    # Keep test collections isolated while preserving the local default path.
    persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_or_create_collection(name=args.collection, embedding_function=ZeroEmbeddingFunction())

    db = None if args.skip_db else Session()
    indexed = 0
    for file_path in source_dir.rglob("*"):
        if file_path.suffix.lower() not in {".md", ".txt", ".pdf", ".docx"}:
            continue
        try:
            raw_text = load_document(file_path)
        except Exception as e:
            print(f"[WARN] Skipping {file_path}: {e}")
            continue
        chunks = chunk_text(raw_text)
        embeddings = embed_texts(chunks)
        # Prepare metadata for each chunk
        metas = []
        for idx, chunk in enumerate(chunks):
            metas.append({
                "doc_id": str(file_path),
                "title": file_path.stem.replace("_", " ").title(),
                "category": file_path.parent.name,
                "chunk_idx": idx,
                "source_path": str(file_path.resolve()),
            })
        ids = [f"{file_path.stem}_{i}" for i in range(len(chunks))]
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=ids,
            metadatas=metas,
        )
        # Insert a record into DB (one per source doc)
        if db is not None:
            db_doc = knowledge_model.KnowledgeDocument(
                title=file_path.stem.replace("_", " ").title(),
                category=file_path.parent.name,
                content=raw_text,
                source_path=str(file_path.resolve()),
                file_path=str(file_path.resolve()),
                doc_type=file_path.suffix.lower().lstrip("."),
            )
            db.add(db_doc)
        indexed += 1
        print(f"[INFO] Indexed {file_path} -> {len(chunks)} chunks")
    if db is not None:
        db.commit()
        db.close()
    print(f"[DONE] Indexed {indexed} documents into collection '{args.collection}'.")

if __name__ == "__main__":
    main()

