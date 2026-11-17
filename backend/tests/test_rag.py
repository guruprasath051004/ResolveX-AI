"""Tests for RAG ingestion and semantic search.

The test executes the ingestion script, then queries the Chroma collection for a
specific user query and asserts that the top result belongs to the expected
category/document.
"""

import subprocess
import pathlib
import sys
import os
import tempfile
import json


def run_ingest(persist_directory: str):
    env = os.environ.copy()
    env["CHROMA_PERSIST_DIR"] = persist_directory
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.rag.ingest",
            "--source",
            str(pathlib.Path(__file__).resolve().parents[2] / "documents"),
            "--collection",
            "resolvex_docs",
            "--skip-db",
        ],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).resolve().parents[2],
        env=env,
    )
    assert result.returncode == 0, f"Ingestion failed: {result.stderr}"
    print(result.stdout)


def query_collection(query: str, persist_directory: str):
    env = os.environ.copy()
    env["CHROMA_PERSIST_DIR"] = persist_directory
    env["RAG_TEST_QUERY"] = query
    script = """
import json
import os
import chromadb
client = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_DIR"])
collection = client.get_collection(name="resolvex_docs")
from backend.rag.embeddings import embed_texts
result = collection.query(
    query_embeddings=embed_texts([os.environ["RAG_TEST_QUERY"]]),
    n_results=3,
    where={"category": "network"},
)
print("RAG_RESULT=" + json.dumps(result))
client._system.stop()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).resolve().parents[2],
        env=env,
    )
    assert result.returncode == 0, f"Chroma query failed: {result.stderr}"
    result_line = next(
        line.removeprefix("RAG_RESULT=")
        for line in result.stdout.splitlines()
        if line.startswith("RAG_RESULT=")
    )
    return json.loads(result_line)


def test_network_query():
    with tempfile.TemporaryDirectory(prefix="resolvex-chroma-test-") as data_path:
        run_ingest(data_path)
        res = query_collection("company portal not opening on Wi-Fi", data_path)
    # Expect at least one result
    assert res["ids"][0], "No IDs returned"
    # Verify the first result's metadata title indicates network connectivity
    meta = res["metadatas"][0][0]
    assert "network" in meta["category"].lower(), f"Unexpected category: {meta['category']}"
    assert "network connectivity" in meta["title"].lower(), f"Unexpected title: {meta['title']}"
    # Verify the chunk text contains the searched phrase (case‑insensitive)
    chunk = res["documents"][0][0].lower()
    assert "company portal" in chunk, "Chunk does not contain expected phrase"

if __name__ == "__main__":
    # Allow running the test directly via `python -m pytest backend/tests/test_rag.py`
    sys.exit(pytest.main([__file__]))

