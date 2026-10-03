const statsEl = document.querySelector("#stats");
const libraryEl = document.querySelector("#library");
const statusEl = document.querySelector("#status");
const answerEl = document.querySelector("#answer");

function setStatus(text) {
  statusEl.textContent = text || "";
}

async function refresh() {
  const res = await fetch("/procedures");
  const data = await res.json();
  statsEl.textContent = `${data.documents} procedures · ${data.chunks} passages · ${data.diagrams} diagrams`;
  libraryEl.innerHTML = "";
  if (!data.procedures.length) {
    libraryEl.innerHTML = "<li>No procedures indexed yet.</li>";
    return;
  }
  for (const doc of data.procedures) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${doc.title}</span><span>${doc.chunks} passages · ${doc.diagrams} diagrams</span>`;
    libraryEl.appendChild(li);
  }
}

async function post(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return data;
}

document.querySelector("#file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  setStatus("Indexing " + file.name + "…");
  try {
    const body = new FormData();
    body.append("file", file);
    const data = await post("/upload", { method: "POST", body });
    setStatus(`Indexed ${data.filename}: ${data.chunks} passages, ${data.diagrams} diagrams.`);
    await refresh();
  } catch (err) {
    setStatus(err.message);
  } finally {
    event.target.value = "";
  }
});

document.querySelector("#samples").addEventListener("click", async () => {
  setStatus("Loading sample procedures…");
  try {
    const data = await post("/ingest-samples", { method: "POST" });
    setStatus(`Library now has ${data.documents} procedures and ${data.diagrams} diagrams.`);
    await refresh();
  } catch (err) {
    setStatus(err.message);
  }
});

document.querySelector("#reset").addEventListener("click", async () => {
  setStatus("Clearing…");
  try {
    await post("/reset", { method: "POST" });
    answerEl.hidden = true;
    setStatus("Library cleared.");
    await refresh();
  } catch (err) {
    setStatus(err.message);
  }
});

document.querySelector("#ask-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.querySelector("#question").value.trim();
  if (!question) return;
  setStatus("Searching…");
  answerEl.hidden = true;
  try {
    const data = await post("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 4 }),
    });
    const sources = (data.sources || [])
      .map((src) => {
        const image = src.diagram_id
          ? `<img alt="Diagram from ${src.filename} page ${src.page}" src="/diagrams/${src.diagram_id}" />`
          : "";
        return `<div class="source"><div class="tag">${src.kind} · page ${src.page} · ${src.filename}</div><p>${escapeHtml(src.content)}</p>${image}</div>`;
      })
      .join("");
    answerEl.innerHTML = `<pre>${escapeHtml(data.answer)}</pre>${sources}`;
    answerEl.hidden = false;
    setStatus("");
  } catch (err) {
    setStatus(err.message);
  }
});

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

refresh().catch(() => {
  statsEl.textContent = "API not reachable";
});
