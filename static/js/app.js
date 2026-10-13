/* ── DOM refs ─────────────────────────────────────────── */
const html        = document.documentElement;
const welcomeEl   = document.getElementById("welcome");
const messagesEl  = document.getElementById("messages");
const chatForm    = document.getElementById("chatForm");
const questionEl  = document.getElementById("question");
const sendBtn     = document.getElementById("sendBtn");
const themeToggle = document.getElementById("themeToggle");
const menuBtn     = document.getElementById("menuBtn");
const sidebar     = document.getElementById("sidebar");
const newChatBtn  = document.getElementById("newChatBtn");

/* Trace drawer */
const traceDrawer  = document.getElementById("traceDrawer");
const traceOverlay = document.getElementById("traceOverlay");
const traceSteps   = document.getElementById("traceSteps");
const traceSource  = document.getElementById("traceSource");
const closeTrace   = document.getElementById("closeTrace");

/* Upload modal */
const uploadModal  = document.getElementById("uploadModal");
const fileInput    = document.getElementById("fileInput");
const fileLabel    = document.getElementById("fileLabel");
const fileDrop     = document.getElementById("fileDrop");

/* ── Theme ────────────────────────────────────────────── */
const savedTheme = localStorage.getItem("theme") || "dark";
html.setAttribute("data-theme", savedTheme);

themeToggle.addEventListener("click", () => {
  const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
});

/* ── Sidebar toggle ───────────────────────────────────── */
menuBtn.addEventListener("click", () => {
  sidebar.classList.toggle("open");
  sidebar.classList.toggle("collapsed");
});

newChatBtn.addEventListener("click", () => {
  messagesEl.innerHTML = "";
  welcomeEl.style.display = "flex";
  messagesEl.style.display = "none";
  questionEl.value = "";
  questionEl.style.height = "auto";
  sendBtn.disabled = true;
  if (window.innerWidth <= 900) sidebar.classList.remove("open");
});

/* ── Helpers ──────────────────────────────────────────── */
function escapeHtml(s = "") {
  return s.replace(/[&<>'"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]
  );
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// Render markdown safely for AI output
function renderMarkdown(text = "") {
  marked.setOptions({ breaks: true, gfm: true });
  return marked.parse(text);
}

function showChat() {
  welcomeEl.style.display = "none";
  messagesEl.style.display = "flex";
}

/* ── Auto-resize textarea ─────────────────────────────── */
questionEl.addEventListener("input", () => {
  sendBtn.disabled = !questionEl.value.trim();
  questionEl.style.height = "auto";
  questionEl.style.height = Math.min(questionEl.scrollHeight, 160) + "px";
});

questionEl.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) chatForm.dispatchEvent(new Event("submit"));
  }
});

/* ── Add user message ─────────────────────────────────── */
function addUserMessage(text) {
  showChat();
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
  messagesEl.appendChild(row);
  scrollBottom();
}

/* ── Add AI message shell (returns content div) ───────── */
function addAiShell() {
  const row = document.createElement("div");
  row.className = "msg-row ai";
  row.innerHTML = `
    <div class="ai-avatar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" fill="currentColor"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
    </div>
    <div class="ai-content">
      <div class="ai-text" id="streaming-text"></div>
      <div class="ai-meta" id="ai-meta" style="display:none"></div>
    </div>`;
  messagesEl.appendChild(row);
  scrollBottom();
  return {
    textEl: row.querySelector("#streaming-text"),
    metaEl: row.querySelector("#ai-meta"),
  };
}

/* ── Show thinking dots ───────────────────────────────── */
function showThinking(textEl) {
  textEl.innerHTML = `<div class="thinking-dots"><span></span><span></span><span></span></div>`;
}

/* ── Scroll to bottom ─────────────────────────────────── */
function scrollBottom() {
  const main = document.getElementById("chatMain");
  main.scrollTop = main.scrollHeight;
}

/* ── Render trace drawer ──────────────────────────────── */
function openTrace(steps, source) {
  traceSteps.innerHTML = steps
    .map(s => `<div class="trace-step">${escapeHtml(s)}</div>`)
    .join("");
  traceSource.textContent = source || "—";
  traceDrawer.classList.add("open");
  traceOverlay.classList.add("show");
}

closeTrace.addEventListener("click", closeTraceDrawer);
traceOverlay.addEventListener("click", closeTraceDrawer);

function closeTraceDrawer() {
  traceDrawer.classList.remove("open");
  traceOverlay.classList.remove("show");
}

/* ── Main ask function (POST + client-side typewriter) ── */
async function askAgent(question) {
  addUserMessage(question);
  questionEl.value = "";
  questionEl.style.height = "auto";
  sendBtn.disabled = true;

  const { textEl, metaEl } = addAiShell();
  showThinking(textEl);

  try {
    // Use plain POST — works everywhere including Render/proxies
    // SSE/EventSource is unreliable behind reverse proxies on free hosting
    const controller = new AbortController();
    const timeoutId  = setTimeout(() => controller.abort(), 120000); // 2 min timeout

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");

    const answer     = data.answer      || "";
    const sourceUsed = data.source_used || "";
    const citations  = data.citations   || [];
    const traceLog   = data.trace       || [];

    // Remove thinking dots
    textEl.innerHTML = "";

    // Typewriter effect — stream words client-side from the full response
    await typewriterEffect(textEl, answer);

    // Render final markdown
    textEl.innerHTML = renderMarkdown(answer);

    // Build meta row
    const sourceLabel = sourceUsed
      ? `<span class="source-tag">
           <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
           ${escapeHtml(sourceUsed.replace(/_/g, " "))}
         </span>` : "";

    const traceLabel = traceLog.length
      ? `<button class="trace-btn" id="open-trace-btn">
           <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
           View trace
         </button>` : "";

    const citeHtml = citations.length
      ? `<div class="citations-list"><strong style="font-size:12px;color:var(--text-dim)">Sources</strong>${
          citations.map(c => c.url
            ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.title)}</a>`
            : escapeHtml(c.title)
          ).join("")
        }</div>` : "";

    metaEl.innerHTML = sourceLabel + traceLabel;
    if (citeHtml) metaEl.insertAdjacentHTML("afterend", citeHtml);
    metaEl.style.display = "flex";

    const traceButton = document.getElementById("open-trace-btn");
    if (traceButton) {
      traceButton.addEventListener("click", () => openTrace(traceLog, sourceUsed));
    }

  } catch (err) {
    const msg = err.name === "AbortError"
      ? "Request timed out. The server may be waking from sleep — please try again."
      : `Something went wrong: ${escapeHtml(err.message)}`;
    textEl.innerHTML = `<span style="color:#f28b82">${msg}</span>`;
  } finally {
    sendBtn.disabled = false;
    questionEl.focus();
    scrollBottom();
  }
}

/* ── Typewriter effect ────────────────────────────────── */
async function typewriterEffect(textEl, fullText) {
  const words = fullText.split(" ");
  let displayed = "";
  for (let i = 0; i < words.length; i++) {
    displayed += (i === 0 ? "" : " ") + words[i];
    textEl.innerHTML = escapeHtml(displayed).replace(/\n/g, "<br>")
      + '<span class="cursor"></span>';
    scrollBottom();
    // Slight delay between words — feels natural, not too slow
    await sleep(18);
  }
}

/* ── Form submit ──────────────────────────────────────── */
chatForm.addEventListener("submit", e => {
  e.preventDefault();
  const q = questionEl.value.trim();
  if (q) askAgent(q);
});

/* ── Suggestion cards ─────────────────────────────────── */
document.querySelectorAll(".suggestion-card").forEach(btn => {
  btn.addEventListener("click", () => askAgent(btn.dataset.q));
});

/* ── Upload modal ─────────────────────────────────────── */
document.getElementById("openUpload").addEventListener("click", () => {
  uploadModal.classList.remove("hidden");
  if (window.innerWidth <= 900) sidebar.classList.remove("open");
});

document.getElementById("closeUpload").addEventListener("click", () =>
  uploadModal.classList.add("hidden")
);

uploadModal.addEventListener("click", e => {
  if (e.target === uploadModal) uploadModal.classList.add("hidden");
});

fileInput.addEventListener("change", () => {
  fileLabel.textContent = fileInput.files[0]?.name || "Click to browse or drag & drop";
});

fileDrop.addEventListener("dragover",  e => { e.preventDefault(); fileDrop.classList.add("drag-over"); });
fileDrop.addEventListener("dragleave", ()  => fileDrop.classList.remove("drag-over"));
fileDrop.addEventListener("drop", e => {
  e.preventDefault();
  fileDrop.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) {
    fileInput.files = e.dataTransfer.files;
    fileLabel.textContent = e.dataTransfer.files[0].name;
  }
});

document.getElementById("uploadBtn").addEventListener("click", async () => {
  const file   = fileInput.files[0];
  const key    = document.getElementById("adminKey").value.trim();
  const status = document.getElementById("uploadStatus");

  if (!file) { status.textContent = "Please choose a file."; status.className = "upload-status err"; return; }
  if (!key)  { status.textContent = "Admin key is required."; status.className = "upload-status err"; return; }

  status.textContent = "Indexing…";
  status.className = "upload-status";

  const fd = new FormData();
  fd.append("file", file);

  try {
    const r = await fetch("/api/ingest", {
      method: "POST",
      headers: { "X-Admin-Key": key },
      body: fd,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Upload failed");
    status.textContent = `✓ "${d.file}" indexed — ${d.chunks} chunks`;
    status.className = "upload-status ok";
    fileLabel.textContent = "Click to browse or drag & drop";
    fileInput.value = "";
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
    status.className = "upload-status err";
  }
});
