"""
main.py
-------
FastAPI entry point for the beginner RAG app.

Endpoints:
  GET  /health          — is the server up?
  GET  /stats           — how many chunks are indexed?
  POST /upload          — upload a PDF, parse (text+tables), chunk, embed, store
  POST /ask             — ask a question over the indexed PDFs
  POST /reset           — clear the vector store (start fresh)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from chunking import chunk_documents
from pdf_parser import extract_pdf_content, pages_to_documents
from rag import (
    UPLOAD_DIR,
    ask,
    collection_stats,
    ensure_dirs,
    index_chunks,
    reset_collection,
)

app = FastAPI(
    title="Beginner RAG API",
    description="Upload PDFs (text + tables) and ask questions with ChromaDB.",
    version="1.0.0",
)

# Allow the Vite React app (default http://localhost:5173) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question")
    top_k: int = Field(4, ge=1, le=10, description="How many chunks to retrieve")


@app.on_event("startup")
def on_startup() -> None:
    """Make sure data folders exist when the server boots."""
    ensure_dirs()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/stats")
def stats() -> dict:
    return collection_stats()


@app.post("/reset")
def reset() -> dict:
    """Wipe the ChromaDB collection so you can re-index from scratch."""
    reset_collection()
    return {"status": "reset", **collection_stats()}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    """
    Accept a PDF upload, extract text + tables, chunk, embed, and store in ChromaDB.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a .pdf file")

    ensure_dirs()
    # Keep the original filename but avoid path tricks (security basics)
    safe_name = Path(file.filename).name
    dest = UPLOAD_DIR / safe_name

    try:
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    # 1) Parse PDF → pages with text + tables
    pages = extract_pdf_content(dest)
    if not pages:
        raise HTTPException(
            status_code=400,
            detail="No extractable text or tables found in this PDF.",
        )

    # 2) Flatten into documents, then chunk
    documents = pages_to_documents(pages, source_name=safe_name)
    chunks = chunk_documents(documents)

    # 3) Embed + store in ChromaDB
    indexed = index_chunks(chunks)

    return {
        "filename": safe_name,
        "pages": len(pages),
        "documents": len(documents),
        "chunks_indexed": indexed,
        **collection_stats(),
    }


@app.post("/ask")
def ask_question(body: AskRequest) -> dict:
    """Retrieve relevant chunks and produce an answer (+ sources)."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return ask(question, top_k=body.top_k)
