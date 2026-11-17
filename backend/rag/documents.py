"""Supported knowledge document loaders and chunking."""

import pathlib


SUPPORTED_EXTENSIONS = {".docx", ".md", ".pdf", ".txt"}


def load_document(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        from pdfminer.high_level import extract_text

        return extract_text(str(path))
    if suffix == ".docx":
        import docx2txt

        return docx2txt.process(str(path))
    raise ValueError(f"Unsupported file type: {suffix}")


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 50) -> list[str]:
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap must be smaller than chunk size")
    words = text.split()
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + chunk_size]))
    return chunks
