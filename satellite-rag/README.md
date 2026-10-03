# Offline satellite procedure desk

A second, smaller RAG app for **procedure PDFs that include diagrams**. It is built to keep working after you disconnect from the internet.

The first app (`backend/` + `frontend/`) is a general PDF demo. This one is the offline procedure library.

## Offline architecture

| Piece | Choice | Why it stays offline |
|--------|--------|----------------------|
| Database | **SQLite** file `backend/data/satellite.db` | No database server |
| Vectors | Stored **inside SQLite** | No Chroma server, no cloud vector DB |
| Embeddings | `all-MiniLM-L6-v2` on CPU | Free local model |
| Diagrams | Images extracted from the PDF + **Tesseract OCR** | Local binary, files on disk |
| Answers | Retrieval of the closest passages | No LLM API |
| UI | One HTML page served by FastAPI | No Node server, no CDN |

Download the embedding model once while you still have a network. After that you can run with:

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

Tesseract must be installed locally (`tesseract` on your PATH). On Debian/Ubuntu: `sudo apt install tesseract-ocr`.

## Layout

```
satellite-rag/
  procedures/          sample procedure PDFs (text + table + diagram)
  backend/
    main.py            API + static UI
    db.py              SQLite schema
    ingest.py          text, tables, diagram images, OCR
    search.py          local cosine search
    static/            basic frontend
    create_samples.py  rebuild the sample PDFs
```

## Setup

```bash
cd satellite-rag/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You also need the `tesseract` program, not just the Python package.

## Run

```bash
cd satellite-rag/backend
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8010
```

Open http://127.0.0.1:8010

1. Click **Load sample procedures** (or upload your own PDFs).
2. Ask a question, for example: `What bus voltage is required before the payload is connected?`
3. Passages from the matching procedure show under the answer. Diagram hits include the extracted image.

## Samples

- `procedures/SAT-PWR-001-power-up.pdf` — power-up steps, voltage table, power-path diagram
- `procedures/SAT-SAFE-002-safe-mode.pdf` — safe-mode steps, signal table, recovery diagram

Rebuild them with `python create_samples.py` (needs `reportlab` and `pillow`).

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/stats` | Document, passage, and diagram counts |
| GET | `/procedures` | What is indexed |
| POST | `/upload` | One PDF (`file` form field) |
| POST | `/ingest-samples` | Index `procedures/*.pdf` |
| POST | `/ask` | JSON `{"question": "...", "top_k": 4}` |
| GET | `/diagrams/{id}` | Extracted diagram image |
| POST | `/reset` | Wipe the library |

## Limits

- Scanned pages with no embedded image and no text still need a real OCR pass of the whole page. This app OCRs **embedded diagram images**, and reads normal text with pdfplumber.
- Search is nearest-passage retrieval, not a generated paragraph. That is what lets it run with no API key and no local LLM.
- Fine for a procedure library on one machine. It scans every stored vector in SQLite, which is the simple approach.
