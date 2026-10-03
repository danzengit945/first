"""
chunking.py
-----------
Split long documents into smaller overlapping chunks.

Why chunk?
  Embedding models have a max input size, and smaller chunks retrieve
  more precisely. Overlap helps keep sentences from being cut mid-thought.
"""

from __future__ import annotations


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    Split `text` into overlapping character-based chunks.

    This is intentionally simple (character counts, not tokens) so beginners
    can follow the logic without a tokenizer.

    Args:
        text: The full text to split.
        chunk_size: Max characters per chunk.
        chunk_overlap: How many characters of the previous chunk to repeat
                       at the start of the next one.

    Returns:
        A list of chunk strings (empty strings are dropped).
    """
    text = (text or "").strip()
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward, but keep some overlap with the previous chunk
        if end >= text_len:
            break
        start = end - chunk_overlap

    return chunks


def chunk_documents(
    documents: list[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[dict]:
    """
    Chunk a list of documents from pdf_parser.pages_to_documents().

    Each output item keeps the parent metadata and adds a chunk_index.
    """
    chunked: list[dict] = []

    for doc in documents:
        pieces = chunk_text(doc["content"], chunk_size, chunk_overlap)
        for i, piece in enumerate(pieces):
            chunked.append(
                {
                    "content": piece,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_index": i,
                    },
                }
            )

    return chunked
