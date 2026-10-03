"""
pdf_parser.py
-------------
Extract readable content from a PDF:
  1. Normal paragraph text
  2. Tables (converted to a markdown-like text so they can be embedded)

We use pdfplumber because it handles both text and tables well for beginners.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber


def _table_to_text(table: list[list[str | None]]) -> str:
    """
    Turn a pdfplumber table (list of rows) into plain text.

    Example output:
      Name | Age | City
      ---
      Ada | 36 | London
      Bob | 28 | Paris
    """
    if not table:
        return ""

    # Replace None cells with empty strings and strip whitespace
    rows: list[list[str]] = []
    for row in table:
        cells = [(cell or "").strip().replace("\n", " ") for cell in row]
        # Skip completely empty rows
        if any(cells):
            rows.append(cells)

    if not rows:
        return ""

    lines: list[str] = []
    header = " | ".join(rows[0])
    lines.append(header)
    lines.append("---")
    for row in rows[1:]:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def extract_pdf_content(pdf_path: str | Path) -> list[dict]:
    """
    Parse a PDF into a list of page-level content blocks.

    Each item looks like:
      {
        "page": 1,
        "text": "...paragraph text...",
        "tables": ["col1 | col2\\n---\\n...", ...]
      }

    Returns one dict per page that had any content.
    """
    pdf_path = Path(pdf_path)
    pages: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # --- Plain text ---
            # extract_text() returns None on empty pages
            raw_text = page.extract_text() or ""
            text = raw_text.strip()

            # --- Tables ---
            # extract_tables() returns a list of tables; each table is a list of rows
            raw_tables = page.extract_tables() or []
            table_texts = []
            for table in raw_tables:
                rendered = _table_to_text(table)
                if rendered:
                    table_texts.append(rendered)

            if text or table_texts:
                pages.append(
                    {
                        "page": page_number,
                        "text": text,
                        "tables": table_texts,
                    }
                )

    return pages


def pages_to_documents(pages: list[dict], source_name: str) -> list[dict]:
    """
    Flatten page content into "documents" ready for chunking.

    Each document is a dict with:
      - content: the text we will embed
      - metadata: source file name, page number, and content type (text/table)
    """
    documents: list[dict] = []

    for page in pages:
        page_num = page["page"]

        if page["text"]:
            documents.append(
                {
                    "content": page["text"],
                    "metadata": {
                        "source": source_name,
                        "page": page_num,
                        "type": "text",
                    },
                }
            )

        for i, table_text in enumerate(page["tables"], start=1):
            documents.append(
                {
                    "content": f"[Table {i} on page {page_num}]\n{table_text}",
                    "metadata": {
                        "source": source_name,
                        "page": page_num,
                        "type": "table",
                    },
                }
            )

    return documents
