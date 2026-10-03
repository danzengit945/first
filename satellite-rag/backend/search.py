"""
Local retrieve step.

The question is embedded with the same MiniLM model used at index time.
We compare it to every stored vector with a dot product (the vectors are
normalized, so that is cosine similarity). SQLite holds the vectors;
nothing leaves the machine.
"""

from __future__ import annotations

import sqlite3
from array import array

from sentence_transformers import SentenceTransformer

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # CPU only — works on a laptop with no GPU and no network
        # (after the model files have been downloaded once).
        _model = SentenceTransformer(EMBED_MODEL, device="cpu")
    return _model


def embed_texts(texts: list[str]) -> list[bytes]:
    """Return one float32 blob per text, ready to store in SQLite."""
    if not texts:
        return []
    vectors = get_model().encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    blobs: list[bytes] = []
    for vector in vectors:
        blobs.append(array("f", (float(x) for x in vector)).tobytes())
    return blobs


def _dot(query: array, stored: bytes) -> float:
    other = array("f")
    other.frombytes(stored)
    return sum(a * b for a, b in zip(query, other))


def ask(conn: sqlite3.Connection, question: str, top_k: int = 4) -> dict:
    """Return the best matching procedure passages and any linked diagrams."""
    rows = conn.execute(
        """
        SELECT c.id, c.page, c.kind, c.content, c.embedding,
               d.filename, d.title,
               g.id AS diagram_id, g.image_path, g.ocr_text
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        LEFT JOIN diagrams g ON g.id = c.diagram_id
        """
    ).fetchall()

    if not rows:
        return {
            "answer": "No procedures are indexed yet. Upload a PDF or load the samples.",
            "sources": [],
            "mode": "offline-retrieval",
        }

    query_blob = embed_texts([question])[0]
    query = array("f")
    query.frombytes(query_blob)

    scored = []
    for row in rows:
        score = _dot(query, row["embedding"])
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[: max(1, min(top_k, len(scored)))]

    sources = []
    lines = [
        "Offline answer: the closest passages from your procedure library.",
        f'Question: "{question}"',
        "",
    ]
    for rank, (score, row) in enumerate(top, start=1):
        lines.append(
            f"{rank}. {row['filename']} — page {row['page']} ({row['kind']}, score {score:.2f})"
        )
        lines.append(row["content"])
        lines.append("")
        sources.append(
            {
                "filename": row["filename"],
                "title": row["title"],
                "page": row["page"],
                "kind": row["kind"],
                "content": row["content"],
                "score": round(float(score), 4),
                "diagram_id": row["diagram_id"],
                "image_path": row["image_path"],
            }
        )

    return {
        "answer": "\n".join(lines).strip(),
        "sources": sources,
        "mode": "offline-retrieval",
    }
