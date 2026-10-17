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
const uploadModal = document.getElementById("uploadModal");
const fileInput   = document.getElementById("fileInput");
const fileLabel   = document.getElementById("fileLabel");
const fileDrop    = document.getElementById("fileDrop");
let requestInFlight = false;

/* ── Theme ────────────────────────────────────────────── */
const savedTheme = localStorage.getItem("theme") || "dark";
html.setAttribute("data-theme", savedTheme);

themeToggle.addEventListener("click", () => {
  const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
});

/* ── Sidebar ──────────────────────────────────────────── */
menuBtn.addEventListener("click", () => sidebar.classList.toggle("open"));

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

function renderMarkdown(text = "") {
  if (typeof marked === "undefined") {
    return escapeHtml(text).replace(/\n/g, "<br>");
  }
  marked.setOptions({ breaks: true, gfm: true });
  return marked.parse(text);
}

function showChat() {
  welcomeEl.style.display = "none";
  messagesEl.style.display = "flex";
}

function scrollBottom() {
  document.getElementById("chatMain").scrollTop = 99999;
}

/* ── Textarea auto-resize ─────────────────────────────── */
questionEl.addEventListener("input", () => {
  sendBtn.disabled = requestInFlight || !questionEl.value.trim();
  questionEl.style.height = "auto";
  questionEl.style.height = Math.min(questionEl.scrollHeight, 160) + "px";
});

questionEl.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) chatForm.dispatchEvent(new Event("submit"));
  }
});

/* ── Add messages ─────────────────────────────────────── */
function addUserMessage(text) {
  showChat();
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `<div class="user-bubble">${escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
  messagesEl.appendChild(row);
  scrollBottom();
}

function addAiShell() {
  const row = document.createElement("div");
  row.className = "msg-row ai";
  // Use unique IDs per message to avoid querySelector conflicts
  const uid = Date.now();
  row.innerHTML = `
    <div class="ai-avatar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="3" fill="currentColor"/>
        <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"
          stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="ai-content">
      <div class="ai-text" id="text-${uid}"></div>
      <div class="ai-meta" id="meta-${uid}" style="display:none"></div>
    </div>`;
  messagesEl.appendChild(row);
  scrollBottom();
  return {
    textEl: row.querySelector(`#text-${uid}`),
    metaEl: row.querySelector(`#meta-${uid}`),
  };
}

function showThinking(textEl) {
  textEl.innerHTML = `<div class="thinking-dots"><span></span><span></span><span></span></div>`;
}

/* ── Trace drawer ─────────────────────────────────────── */
function openTrace(steps, source) {
  traceSteps.innerHTML = steps.map(s => `<div class="trace-step">${escapeHtml(s)}</div>`).join("");
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

/* ── Meta row ─────────────────────────────────────────── */
function buildMeta(metaEl, sourceUsed, traceLog, citations) {
  const sourceLabel = sourceUsed
    ? `<span class="source-tag">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
        ${escapeHtml(sourceUsed.replace(/_/g, " "))}
       </span>` : "";

  const traceId = "trace-btn-" + Date.now();
  const traceLabel = traceLog.length
    ? `<button class="trace-btn" id="${traceId}">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        View trace
       </button>` : "";

  const citeHtml = citations.length
    ? `<div class="citations-list"><strong style="font-size:12px;color:var(--text-dim)">Sources</strong>${
        citations.map(c => c.url
          ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.title)}</a>`
          : escapeHtml(c.title)).join("")
      }</div>` : "";

  metaEl.innerHTML = sourceLabel + traceLabel;
  if (citeHtml) metaEl.insertAdjacentHTML("afterend", citeHtml);
  if (sourceLabel || traceLabel) metaEl.style.display = "flex";

  if (traceLog.length) {
    document.getElementById(traceId)?.addEventListener("click", () => openTrace(traceLog, sourceUsed));
  }
}

/* ── Typewriter ───────────────────────────────────────── */
async function typewriter(textEl, text) {
  const words = text.split(" ");
  let built = "";
  for (let i = 0; i < words.length; i++) {
    built += (i === 0 ? "" : " ") + words[i];
    textEl.innerHTML = escapeHtml(built).replace(/\n/g, "<br>") + '<span class="cursor"></span>';
    scrollBottom();
    await sleep(15);
  }
}

/* ── Core ask function — plain POST, always works ─────── */
async function askAgent(question) {
  if (requestInFlight) return;
  requestInFlight = true;
  addUserMessage(question);
  questionEl.value = "";
  questionEl.style.height = "auto";
  sendBtn.disabled = true;

  const { textEl, metaEl } = addAiShell();
  showThinking(textEl);
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 100000);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });

    // Always read as text first — never assume JSON
    const raw = await res.text();

    if (!raw || raw.trim() === "") {
      throw new Error("Server returned an empty response. Please try again.");
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error("Server error: " + raw.slice(0, 150));
    }

    if (!res.ok) {
      throw new Error(data.detail || `Server error ${res.status}`);
    }

    const answer   = data.answer      || "No answer returned.";
    const source   = data.source_used || "";
    const trace    = data.trace       || [];
    const citations = data.citations  || [];

    // Animate the answer word by word
    await typewriter(textEl, answer);

    // Render as markdown once animation is done
    textEl.innerHTML = renderMarkdown(answer);

    buildMeta(metaEl, source, trace, citations);

  } catch (err) {
    const message = err.name === "AbortError"
      ? "The request timed out. Please try again or check the server logs."
      : err.message || "The request failed. Please try again.";
    textEl.innerHTML = `<span style="color:#f28b82">⚠ ${escapeHtml(message)}</span>`;
  } finally {
    window.clearTimeout(timeoutId);
    requestInFlight = false;
    sendBtn.disabled = !questionEl.value.trim();
    questionEl.focus();
    scrollBottom();
  }
}

/* ── Form submit ──────────────────────────────────────── */
chatForm.addEventListener("submit", e => {
  e.preventDefault();
  if (requestInFlight) return;
  const q = questionEl.value.trim();
  if (q) askAgent(q);
});

/* ── Suggestion cards ─────────────────────────────────── */
document.querySelectorAll(".suggestion-card").forEach(btn =>
  btn.addEventListener("click", () => askAgent(btn.dataset.q))
);

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
