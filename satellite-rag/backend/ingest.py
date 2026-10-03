"""
Read a procedure PDF into passages a RAG app can search.

Each PDF can contain:
  - normal procedure text (steps, warnings, notes)
  - tables (limits, pinouts, timelines)
  - diagrams (embedded images). We save the image and OCR it locally
    so a question can still find the drawing when the network is off.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pdfplumber
from PIL import Image
from pypdf import PdfReader

from db import DIAGRAM_DIR


def _table_to_text(table: list[list[str | None]]) -> str:
    """Turn a pdfplumber table into plain text lines."""
    rows: list[list[str]] = []
    for row in table or []:
        cells = [(cell or "").strip().replace("\n", " ") for cell in row]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    lines = [" | ".join(rows[0]), "---"]
    for row in rows[1:]:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def _ocr_image(path: Path) -> str:
    """
    Read words inside a diagram with Tesseract (local binary).

    If tesseract is not installed, we still keep the image — search
    will use the page caption instead of OCR text.
    """
    try:
        import pytesseract

        # Scale up and ask Tesseract for a single text block. Diagram
        # labels are often too small in the raw PDF image.
        image = Image.open(path).convert("L")
        image = image.resize(
            (image.width * 2, image.height * 2),
            Image.Resampling.LANCZOS,
        )
        text = pytesseract.image_to_string(image, config="--psm 6")
        return " ".join(text.split())
    except Exception:
        return ""


def _save_embedded_images(pdf_path: Path, doc_stem: str) -> list[dict]:
    """
    Pull raster images out of the PDF (the usual way diagrams are stored).

    Returns a list of {page, image_path, ocr_text}. Page numbers are 1-based.
    """
    saved: list[dict] = []
    reader = PdfReader(str(pdf_path))

    for page_index, page in enumerate(reader.pages):
        page_num = page_index + 1
        try:
            images = list(page.images)
        except Exception:
            images = []

        for image_index, image in enumerate(images, start=1):
            dest = DIAGRAM_DIR / f"{doc_stem}_p{page_num}_{image_index}.png"
            try:
                image.image.save(dest, format="PNG")
            except Exception:
                # Some PDFs embed odd formats. Skip that one image and continue.
                continue
            saved.append(
                {
                    "page": page_num,
                    "image_path": dest.name,
                    "ocr_text": _ocr_image(dest),
                }
            )
    return saved


def _chunk_text(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def parse_procedure(pdf_path: Path) -> tuple[str, list[dict], list[dict]]:
    """
    Parse one PDF.

    Returns:
      title, text/table chunk dicts (no embedding yet), diagram dicts
    """
    pdf_path = Path(pdf_path)
    stem = pdf_path.stem.replace(" ", "_")
    diagrams = _save_embedded_images(pdf_path, stem)
    diagrams_by_page: dict[int, list[dict]] = {}
    for diagram in diagrams:
        diagrams_by_page.setdefault(diagram["page"], []).append(diagram)

    passages: list[dict] = []
    title = pdf_path.stem

    with pdfplumber.open(pdf_path) as pdf:
        if pdf.pages:
            first = (pdf.pages[0].extract_text() or "").strip()
            if first:
                title = first.splitlines()[0][:120]

        for page_num, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                for piece in _chunk_text(text):
                    passages.append(
                        {
                            "page": page_num,
                            "kind": "text",
                            "content": piece,
                            "diagram": None,
                        }
                    )

            for table in page.extract_tables() or []:
                rendered = _table_to_text(table)
                if not rendered:
                    continue
                passages.append(
                    {
                        "page": page_num,
                        "kind": "table",
                        "content": f"[Table on page {page_num}]\n{rendered}",
                        "diagram": None,
                    }
                )

            # Keep a caption line from the page so a diagram is still
            # searchable when OCR only catches part of the drawing.
            caption = ""
            for line in text.splitlines():
                lower = line.lower()
                if "diagram" in lower or "figure" in lower:
                    caption = line.strip()
                    break

            # One searchable passage per diagram, tied to the image file.
            for diagram in diagrams_by_page.get(page_num, []):
                ocr = diagram["ocr_text"] or "(no text detected inside the image)"
                parts = [f"[Diagram on page {page_num} of {pdf_path.name}]"]
                if caption:
                    parts.append(caption)
                parts.append(f"Text read from the drawing: {ocr}")
                passages.append(
                    {
                        "page": page_num,
                        "kind": "diagram",
                        "content": "\n".join(parts),
                        "diagram": diagram,
                    }
                )

    return title, passages, diagrams


def insert_procedure(
    conn: sqlite3.Connection,
    filename: str,
    title: str,
    passages: list[dict],
    embeddings: list[bytes],
) -> dict:
    """
    Write one procedure into SQLite.

    `embeddings[i]` matches `passages[i]` (raw float32 bytes).
    """
    if len(passages) != len(embeddings):
        raise ValueError("Each passage needs one embedding")

    cur = conn.execute(
        "INSERT INTO documents (filename, title) VALUES (?, ?)",
        (filename, title),
    )
    document_id = int(cur.lastrowid)

    # Insert each diagram once, even if we only have one passage pointing at it.
    diagram_ids: dict[str, int] = {}
    for passage in passages:
        diagram = passage.get("diagram")
        if not diagram:
            continue
        key = diagram["image_path"]
        if key in diagram_ids:
            continue
        row = conn.execute(
            """
            INSERT INTO diagrams (document_id, page, image_path, ocr_text)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, diagram["page"], diagram["image_path"], diagram["ocr_text"]),
        )
        diagram_ids[key] = int(row.lastrowid)

    for passage, embedding in zip(passages, embeddings):
        diagram = passage.get("diagram")
        diagram_id = diagram_ids.get(diagram["image_path"]) if diagram else None
        conn.execute(
            """
            INSERT INTO chunks (document_id, page, kind, content, embedding, diagram_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                passage["page"],
                passage["kind"],
                passage["content"],
                embedding,
                diagram_id,
            ),
        )

    conn.commit()
    return {
        "document_id": document_id,
        "filename": filename,
        "title": title,
        "chunks": len(passages),
        "diagrams": len(diagram_ids),
    }
