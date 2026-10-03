# Run this RAG notebook on Kaggle

Notebook: [`beginner_rag.ipynb`](./beginner_rag.ipynb)

Same pipeline as the local app, in one beginner-friendly notebook:

**PDF (text + tables) → chunks → sentence-transformers embeddings → ChromaDB → ask**

## Steps

1. Open [Kaggle Notebooks](https://www.kaggle.com/code) → **New Notebook**.
2. **File → Import Notebook** and upload `kaggle/beginner_rag.ipynb` from this repo  
   (or copy the file into a Kaggle dataset and open it).
3. In the notebook **Settings** panel, turn **Internet → On**.
4. Run all cells top to bottom.
5. The notebook builds a tiny sample PDF with a revenue table, indexes it, and asks a table-aware question.

### Optional: your own PDF

- Upload a PDF (Add data / upload), then set `PDF_PATH` in the config cell, e.g.  
  `PDF_PATH = Path("/kaggle/input/your-dataset/your.pdf")`
- Re-run from the parse cell onward.

## Kaggle-specific notes

| Topic | What to know |
|--------|----------------|
| Internet | Required for `pip install` and downloading `all-MiniLM-L6-v2` |
| Disk | Writes under `/kaggle/working/rag_demo/` (writable) |
| GPU | Not required (embeddings run on CPU) |
| ChromaDB | Works in the notebook with a local persist path |
| LLM key | Not required — retrieval-only answers show the top passages |

## Local equivalent

For the FastAPI + React UI, see the root [`README.md`](../README.md).
