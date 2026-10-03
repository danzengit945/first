"""
Offline satellite-procedure RAG API.

One process serves both the API and the basic web UI, so you do not
need a separate frontend server or an internet connection at runtime.

  GET  /              — the page
  GET  /health
  GET  /stats
  GET  /procedures
  POST /upload        — one PDF
  POST /ingest-samples — index PDFs shipped in ../procedures
  POST /ask           — question in, passages + diagrams out
  GET  /diagrams/{id} — the extracted image
  POST /reset
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db import DIAGRAM_DIR, UPLOAD_DIR, connect, list_documents, reset, stats
from ingest import insert_procedure, parse_procedure
from search import ask, embed_texts

BASE_DIR = Path(__file__).resolve().parent
PROCEDURES_DIR = BASE_DIR.parent / "procedures"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Offline Satellite Procedure RAG", version="1.0.0")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(4, ge=1, le=8)


def _index_pdf(conn, pdf_path: Path) -> dict:
    title, passages, _diagrams = parse_procedure(pdf_path)
    if not passages:
        raise HTTPException(
            status_code=400,
            detail=f"No text, tables, or diagrams found in {pdf_path.name}",
        )
    embeddings = embed_texts([p["content"] for p in passages])
    return insert_procedure(conn, pdf_path.name, title, passages, embeddings)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "offline"}


@app.get("/stats")
def get_stats() -> dict:
    conn = connect()
    try:
        return stats(conn)
    finally:
        conn.close()


@app.get("/procedures")
def procedures() -> dict:
    conn = connect()
    try:
        return {"procedures": list_documents(conn), **stats(conn)}
    finally:
        conn.close()


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a .pdf procedure")

    dest = UPLOAD_DIR / Path(file.filename).name
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    conn = connect()
    try:
        result = _index_pdf(conn, dest)
        return {**result, **stats(conn)}
    finally:
        conn.close()


@app.post("/ingest-samples")
def ingest_samples() -> dict:
    """Index every sample procedure PDF shipped with this app."""
    pdfs = sorted(PROCEDURES_DIR.glob("*.pdf"))
    if not pdfs:
        raise HTTPException(status_code=404, detail="No sample PDFs in procedures/")

    conn = connect()
    indexed = []
    try:
        already = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM documents")
        }
        for pdf in pdfs:
            if pdf.name in already:
                indexed.append({"filename": pdf.name, "skipped": True})
                continue
            indexed.append(_index_pdf(conn, pdf))
        return {"indexed": indexed, **stats(conn)}
    finally:
        conn.close()


@app.post("/ask")
def ask_question(body: AskRequest) -> dict:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    conn = connect()
    try:
        return ask(conn, question, top_k=body.top_k)
    finally:
        conn.close()


@app.get("/diagrams/{diagram_id}")
def diagram(diagram_id: int) -> FileResponse:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT image_path FROM diagrams WHERE id = ?",
            (diagram_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Diagram not found")
    path = DIAGRAM_DIR / row["image_path"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Diagram file missing")
    return FileResponse(path, media_type="image/png")


@app.post("/reset")
def reset_library() -> dict:
    """Forget indexed procedures and delete extracted diagram files."""
    conn = connect()
    try:
        reset(conn)
    finally:
        conn.close()
    if DIAGRAM_DIR.exists():
        for image in DIAGRAM_DIR.glob("*"):
            if image.is_file():
                image.unlink()
    return {"status": "reset", **get_stats()}


# The UI is plain HTML/CSS/JS — no CDN, no Node server.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
