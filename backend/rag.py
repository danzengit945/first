"""
rag.py
------
The heart of Retrieval-Augmented Generation (RAG):

  1. Embed text chunks with a free local model (sentence-transformers)
  2. Store / search them in ChromaDB (local vector database)
  3. Retrieve the most relevant chunks for a question
  4. Optionally call OpenAI to write a natural-language answer
     (falls back to a simple "show the sources" answer if no API key)
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

# Where ChromaDB writes its files on disk (survives restarts)
DATA_DIR = Path(__file__).resolve().parent / "data"
CHROMA_DIR = DATA_DIR / "chroma"
UPLOAD_DIR = DATA_DIR / "uploads"

COLLECTION_NAME = "pdf_chunks"

# Small, fast, free embedding model (~80MB download on first run)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# How many chunks to pull back for each question
TOP_K = 4


# ---------------------------------------------------------------------------
# Lazy singletons (created on first use so startup stays fast)
# ---------------------------------------------------------------------------

_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None


def ensure_dirs() -> None:
    """Create data folders if they do not exist yet."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def get_embedding_model() -> SentenceTransformer:
    """Load the local embedding model once and reuse it."""
    global _embedding_model
    if _embedding_model is None:
        # device="cpu" keeps things simple and portable
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
    return _embedding_model


def get_chroma_collection():
    """Open (or create) the persistent ChromaDB collection."""
    global _chroma_client
    ensure_dirs()
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convert a list of strings into a list of embedding vectors."""
    model = get_embedding_model()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    # Chroma expects plain Python lists, not numpy arrays
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_chunks(chunks: list[dict]) -> int:
    """
    Embed chunks and upsert them into ChromaDB.

    Returns the number of chunks indexed.
    """
    if not chunks:
        return 0

    collection = get_chroma_collection()
    ids = [str(uuid.uuid4()) for _ in chunks]
    documents = [c["content"] for c in chunks]
    # Chroma metadata values must be str / int / float / bool
    metadatas: list[dict[str, Any]] = []
    for c in chunks:
        meta = c["metadata"]
        metadatas.append(
            {
                "source": str(meta.get("source", "")),
                "page": int(meta.get("page", 0)),
                "type": str(meta.get("type", "text")),
                "chunk_index": int(meta.get("chunk_index", 0)),
            }
        )

    embeddings = embed_texts(documents)

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(chunks)


def collection_stats() -> dict:
    """Return a tiny status summary for the UI."""
    collection = get_chroma_collection()
    return {"chunk_count": collection.count()}


def reset_collection() -> None:
    """Delete and recreate the collection (useful when re-indexing)."""
    ensure_dirs()
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        # Collection may not exist yet — that is fine
        pass
    global _chroma_client
    _chroma_client = client
    client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Retrieval + answering
# ---------------------------------------------------------------------------

def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    """
    Find the `top_k` most similar chunks to `question`.

    Returns a list of {content, metadata, distance}.
    """
    collection = get_chroma_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_texts([question])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for content, meta, dist in zip(docs, metas, dists):
        hits.append(
            {
                "content": content,
                "metadata": meta,
                "distance": float(dist),
            }
        )
    return hits


def _build_context(hits: list[dict]) -> str:
    """Format retrieved chunks into a single context string for the LLM."""
    parts: list[str] = []
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        header = (
            f"[Source {i}] file={meta.get('source')} "
            f"page={meta.get('page')} type={meta.get('type')}"
        )
        parts.append(f"{header}\n{hit['content']}")
    return "\n\n".join(parts)


def _answer_with_openai(question: str, context: str) -> str | None:
    """
    Try to generate an answer with OpenAI.

    Returns None if no API key is set or the call fails — caller handles fallback.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Answer the user's question "
                        "using ONLY the provided context from their PDF. "
                        "If the context does not contain the answer, say so clearly. "
                        "Cite page numbers when possible."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                },
            ],
        )
        return response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 — beginner-friendly single catch
        return f"(OpenAI call failed: {exc})"


def _answer_from_sources(question: str, hits: list[dict]) -> str:
    """
    Free fallback when no OpenAI key is available.

    We do not invent an answer — we show the best matching passages so the
    beginner can still see retrieval working end-to-end.
    """
    if not hits:
        return (
            "No documents are indexed yet. Upload a PDF first, then ask again."
        )

    lines = [
        "Answer (retrieval-only mode — no OPENAI_API_KEY set):",
        f'Based on your question "{question}", here are the most relevant passages:',
        "",
    ]
    for i, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        lines.append(
            f"{i}. From {meta.get('source')} (page {meta.get('page')}, "
            f"{meta.get('type')}):"
        )
        lines.append(hit["content"])
        lines.append("")

    lines.append(
        "Tip: set OPENAI_API_KEY to get a natural-language answer written from these sources."
    )
    return "\n".join(lines)


def ask(question: str, top_k: int = TOP_K) -> dict:
    """
    Full RAG query: retrieve → generate answer → return answer + sources.
    """
    hits = retrieve(question, top_k=top_k)
    context = _build_context(hits)
    llm_answer = _answer_with_openai(question, context) if hits else None
    answer = llm_answer if llm_answer else _answer_from_sources(question, hits)

    sources = [
        {
            "content": hit["content"],
            "source": hit["metadata"].get("source"),
            "page": hit["metadata"].get("page"),
            "type": hit["metadata"].get("type"),
            "distance": hit["distance"],
        }
        for hit in hits
    ]

    return {
        "answer": answer,
        "sources": sources,
        "mode": "openai" if (llm_answer and os.getenv("OPENAI_API_KEY")) else "retrieval-only",
    }
