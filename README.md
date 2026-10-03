# Beginner RAG App

A small, well-commented **Retrieval-Augmented Generation (RAG)** demo:

1. Upload a PDF (normal text **and** tables)
2. Chunk + embed locally (free `sentence-transformers` model)
3. Store vectors in **ChromaDB** on disk
4. Ask a question → retrieve relevant chunks → show an answer with sources

No paid API key is required. If you optionally set `OPENAI_API_KEY`, the backend will write a natural-language answer from the retrieved context. Without it, you still get a clear retrieval-only answer built from the top matching passages.

---

## Project layout

```
backend/          FastAPI API, PDF parsing, chunking, embeddings, ChromaDB
  main.py         HTTP endpoints
  pdf_parser.py   Extract text + tables with pdfplumber
  chunking.py     Split long text into overlapping chunks
  rag.py          Embeddings, ChromaDB, retrieve + answer
  requirements.txt
frontend/         React + Vite UI
  src/App.jsx     Upload PDF, ask questions, show sources
kaggle/           Same RAG idea as a beginner Kaggle notebook
  beginner_rag.ipynb
  README.md       Kaggle-specific setup steps
satellite-rag/    Offline procedure library (SQLite, diagrams, one-page UI)
  README.md
```

---

## Prerequisites

- Python **3.10+**
- Node.js **18+** and npm
- ~500MB disk for the first embedding-model download

---

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The first run downloads `all-MiniLM-L6-v2` (~80MB) for local embeddings.

**Optional — nicer generated answers:**

```bash
export OPENAI_API_KEY=sk-...
# optional:
export OPENAI_MODEL=gpt-4o-mini
```

### 2. Frontend

```bash
cd frontend
npm install
```

---

## Run

Open **two terminals**.

**Terminal A — API** (from `backend/` with the venv active):

```bash
uvicorn main:app --reload --port 8000
```

**Terminal B — UI** (from `frontend/`):

```bash
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173).

The Vite dev server proxies `/api/*` → `http://127.0.0.1:8000`, so the browser never needs CORS tricks beyond what the API already allows.

---

## How to use

1. Click **Choose PDF** and pick any text/table PDF.
2. Wait for indexing (first PDF after install may take a bit while the model loads).
3. Type a question and click **Ask**.
4. Read the answer and the **Sources** list (file name, page, text vs table).

**Clear index** wipes the ChromaDB collection so you can start over.

---

## API cheatsheet

| Method | Path       | Purpose                          |
|--------|------------|----------------------------------|
| GET    | `/health`  | Liveness check                   |
| GET    | `/stats`   | Number of indexed chunks         |
| POST   | `/upload`  | multipart form field `file`      |
| POST   | `/ask`     | JSON `{ "question": "...", "top_k": 4 }` |
| POST   | `/reset`   | Delete all indexed chunks        |

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## What each piece does (beginner map)

| Step | File | Idea |
|------|------|------|
| Parse PDF | `pdf_parser.py` | Pull page text + turn tables into markdown-like text |
| Chunk | `chunking.py` | Split long pages so retrieval is precise |
| Embed + store | `rag.py` | Vectors in ChromaDB under `backend/data/chroma/` |
| Ask | `rag.py` + `main.py` | Embed the question, find nearest chunks, answer |
| UI | `frontend/src/App.jsx` | Upload + ask + show sources |

---

## Data on disk

Created automatically under `backend/data/`:

- `uploads/` — saved PDFs
- `chroma/` — ChromaDB persistence

These folders are gitignored.

---

## Notes / limits

- Best on text-based PDFs (not scanned images without OCR).
- Tables are flattened to text so they can be embedded like any other passage.
- Retrieval-only mode does **not** invent answers; it surfaces the best matching passages.
- Keep scope small: one happy path (upload → index → ask → answer).

## Sample PDF

Try `backend/sample_docs/sample_company_report.pdf` — it has narrative text plus a revenue table so you can see both content types retrieved.

---

## Run on Kaggle

Prefer a notebook? Use [`kaggle/beginner_rag.ipynb`](kaggle/beginner_rag.ipynb):

1. Create a new Kaggle notebook → **File → Import Notebook** → upload `beginner_rag.ipynb`.
2. Turn **Internet → On** in notebook Settings.
3. Run all cells (installs deps, builds a sample PDF with a table, indexes into ChromaDB, asks a question).

Details: [`kaggle/README.md`](kaggle/README.md).

---

## Offline satellite procedures

[`satellite-rag/`](satellite-rag/README.md) is a second app for procedure PDFs (text, tables, and diagrams). It uses a SQLite file, local embeddings, and local OCR so it can run with no network and no API key. Start it with `uvicorn` on port **8010**.
