import { useEffect, useState } from "react";
import "./App.css";

/**
 * App.jsx — the whole UI in one beginner-friendly file.
 *
 * Flow:
 *   1. Upload a PDF  → POST /api/upload
 *   2. Ask a question → POST /api/ask
 *   3. Show the answer + source passages
 */

const API = "/api";

export default function App() {
  const [stats, setStats] = useState({ chunk_count: 0 });
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // Load how many chunks are already indexed when the page opens
  async function refreshStats() {
    try {
      const res = await fetch(`${API}/stats`);
      if (res.ok) {
        setStats(await res.json());
      }
    } catch {
      // Backend might not be running yet — that's ok
    }
  }

  useEffect(() => {
    refreshStats();
  }, []);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setError("");
    setUploadResult(null);
    setUploading(true);

    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch(`${API}/upload`, {
        method: "POST",
        body: form,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      setUploadResult(data);
      setStats({ chunk_count: data.chunk_count });
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
      // Allow re-uploading the same file
      event.target.value = "";
    }
  }

  async function handleAsk(event) {
    event.preventDefault();
    if (!question.trim()) return;

    setError("");
    setResult(null);
    setAsking(true);

    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), top_k: 4 }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Ask failed");
      }

      setResult(data);
    } catch (err) {
      setError(err.message || "Ask failed");
    } finally {
      setAsking(false);
    }
  }

  async function handleReset() {
    setError("");
    try {
      const res = await fetch(`${API}/reset`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Reset failed");
      setStats({ chunk_count: data.chunk_count });
      setUploadResult(null);
      setResult(null);
    } catch (err) {
      setError(err.message || "Reset failed");
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <p className="brand">Beginner RAG</p>
        <h1>Ask your PDFs</h1>
        <p className="lede">
          Upload a PDF (text and tables), index it locally with ChromaDB, then
          ask a question. Embeddings run on your machine — no API key required.
        </p>
      </header>

      <main className="layout">
        <section className="panel" aria-labelledby="upload-heading">
          <div className="panel-head">
            <h2 id="upload-heading">1. Upload a PDF</h2>
            <p>
              Indexed chunks: <strong>{stats.chunk_count}</strong>
            </p>
          </div>

          <label className="file-button">
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleUpload}
              disabled={uploading}
            />
            {uploading ? "Indexing…" : "Choose PDF"}
          </label>

          {uploadResult && (
            <p className="success">
              Indexed <strong>{uploadResult.filename}</strong> —{" "}
              {uploadResult.pages} page(s), {uploadResult.chunks_indexed}{" "}
              chunk(s).
            </p>
          )}

          <button
            type="button"
            className="ghost"
            onClick={handleReset}
            disabled={stats.chunk_count === 0}
          >
            Clear index
          </button>
        </section>

        <section className="panel" aria-labelledby="ask-heading">
          <h2 id="ask-heading">2. Ask a question</h2>
          <form onSubmit={handleAsk} className="ask-form">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What does the revenue table show for 2023?"
              rows={4}
              disabled={asking}
            />
            <button type="submit" disabled={asking || !question.trim()}>
              {asking ? "Thinking…" : "Ask"}
            </button>
          </form>
        </section>

        {error && (
          <section className="panel error" role="alert">
            {error}
          </section>
        )}

        {result && (
          <section className="panel answer" aria-labelledby="answer-heading">
            <div className="panel-head">
              <h2 id="answer-heading">Answer</h2>
              <span className="mode">{result.mode}</span>
            </div>
            <pre className="answer-text">{result.answer}</pre>

            {result.sources?.length > 0 && (
              <>
                <h3>Sources</h3>
                <ul className="sources">
                  {result.sources.map((src, i) => (
                    <li key={`${src.source}-${src.page}-${i}`}>
                      <div className="source-meta">
                        <strong>{src.source}</strong>
                        <span>
                          page {src.page} · {src.type}
                        </span>
                      </div>
                      <p>{src.content}</p>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}
      </main>

      <footer className="footer">
        <p>
          Local embeddings via sentence-transformers. Optional natural-language
          answers if you set <code>OPENAI_API_KEY</code>.
        </p>
      </footer>
    </div>
  );
}
