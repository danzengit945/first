"""
SQLite store for the offline satellite RAG app.

Why SQLite?
  It is a single file. No database server to start, and it works
  with the network unplugged. That matches "run completely offline."

What we store:
  documents  — one row per procedure PDF
  diagrams   — extracted images (and OCR text) from those PDFs
  chunks     — text / table / diagram passages plus their embedding
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "satellite.db"
DIAGRAM_DIR = DATA_DIR / "diagrams"
UPLOAD_DIR = DATA_DIR / "uploads"

# all-MiniLM-L6-v2 vectors are 384 floats
EMBED_DIM = 384


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DIAGRAM_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    """Open the database and make sure tables exist."""
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            title TEXT NOT NULL,
            ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS diagrams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            ocr_text TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page INTEGER NOT NULL,
            kind TEXT NOT NULL,          -- text | table | diagram
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,     -- float32 bytes, length EMBED_DIM
            diagram_id INTEGER REFERENCES diagrams(id) ON DELETE SET NULL
        );
        """
    )
    return conn


def stats(conn: sqlite3.Connection) -> dict:
    docs = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
    chunks = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
    diagrams = conn.execute("SELECT COUNT(*) AS n FROM diagrams").fetchone()["n"]
    return {
        "documents": docs,
        "chunks": chunks,
        "diagrams": diagrams,
    }


def list_documents(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT d.id, d.filename, d.title, d.ingested_at,
               (SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.id) AS chunks,
               (SELECT COUNT(*) FROM diagrams g WHERE g.document_id = d.id) AS diagrams
        FROM documents d
        ORDER BY d.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def reset(conn: sqlite3.Connection) -> None:
    """Delete every indexed procedure. Image files are removed by the caller."""
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM diagrams")
    conn.execute("DELETE FROM documents")
    conn.commit()
