// UI logic: sources panel, upload queue, chat. No framework, no build step.
import {
  USE_MOCK, MAX_UPLOAD_MB, ALLOWED_EXTENSIONS, MAX_QUESTION_LENGTH, MAX_ITERATIONS,
  HEALTH_POLL_MS, WIKI_LANGS,
} from "./config.js";
import { api } from "./api.js";
import { renderMarkdown } from "./markdown.js";

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------
const $ = (selector) => document.querySelector(selector);

function lsGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function lsSet(key, value) { try { localStorage.setItem(key, value); } catch { /* ignore */ } }

/** Tiny DOM builder. Text children are always inserted as text (never parsed as HTML). */
function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;            // only used with escaped markdown output
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function uid() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return "id-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

const extOf = (name) => { const i = name.lastIndexOf("."); return i >= 0 ? name.slice(i).toLowerCase() : ""; };

const TYPE_META = {
  pdf: { icon: "📕", label: "PDF" },
  docx: { icon: "📘", label: "DOCX" },
  txt: { icon: "📄", label: "TXT" },
  code: { icon: "💻", label: "Code" },
  pptx: { icon: "📊", label: "Slides" },
  web: { icon: "🌐", label: "Web" },
  wikipedia: { icon: "📖", label: "Wikipedia" },
  audio: { icon: "🎙️", label: "Audio" },
};
const typeMeta = (type) => TYPE_META[type] || { icon: "📄", label: type || "File" };

const FRIENDLY_ERRORS = {
  unsupported_file_type: "This file type is not supported.",
  file_too_large: `The file is larger than ${MAX_UPLOAD_MB} MB.`,
  empty_document: "No readable text was found in this source.",
  invalid_url: "That URL is not valid.",
  invalid_request: "The request was not valid.",
  fetch_failed: "The page could not be downloaded.",
  transcription_failed: "The audio could not be transcribed.",
  no_knowledge_loaded: "Add a source first.",
  network_error: "Cannot reach the backend. Is it running?",
  timeout: "The request took too long and was cancelled.",
};
/** Prefer the server's own message (it is specific); fall back to a generic one by code. */
function friendlyError(err) {
  if (!err) return "Something went wrong.";
  if (err.error === "no_knowledge_loaded") return FRIENDLY_ERRORS.no_knowledge_loaded;
  if (err.detail) return err.detail;
  return FRIENDLY_ERRORS[err.error] || err.message || "Something went wrong.";
}

function toast(message, type = "info", ms = 4500) {
  const node = h("div", { class: `toast ${type}`, role: type === "error" ? "alert" : "status" }, message);
  $("#toasts").append(node);
  setTimeout(() => {
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 260);
  }, ms);
}

function showFieldError(id, message) {
  const node = $(id);
  node.textContent = message || "";
  node.hidden = !message;
}

// ----------------------------------------------------------------------------
// State
// ----------------------------------------------------------------------------
const state = {
  sources: [],
  sourcesLoading: true,
  sourcesError: null,
  uploads: [],            // queue items: { id, name, file, status, text }
  processing: false,
  sessionId: null,
  messages: [],           // { id, role: "user"|"assistant", content?, status?, data?, error?, question? }
  sending: false,
  chatAbort: null,
};
let nextUploadId = 1;

// ----------------------------------------------------------------------------
// Theme, layout, header
// ----------------------------------------------------------------------------
function initChrome() {
  $("#btn-theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    lsSet("theme", next);
  });
  $("#btn-how").addEventListener("click", () => $("#how-dialog").showModal());
  $("#btn-new-chat").addEventListener("click", newChat);

  const open = () => { document.body.classList.add("sidebar-open"); $("#backdrop").hidden = false; };
  const close = () => { document.body.classList.remove("sidebar-open"); $("#backdrop").hidden = true; };
  $("#btn-sidebar").addEventListener("click", open);
  $("#btn-close-sidebar").addEventListener("click", close);
  $("#backdrop").addEventListener("click", close);

  if (USE_MOCK) $("#mock-ribbon").hidden = false;
}

async function pollHealth() {
  const dot = $("#health-dot");
  const text = $("#health-text");
  try {
    const res = await api.health();
    dot.className = "dot ok";
    text.textContent = "Backend online";
    $("#cache-badge").hidden = !!res.redis;
  } catch {
    dot.className = "dot bad";
    text.textContent = "Backend unreachable";
    $("#cache-badge").hidden = true;
  }
}

// ----------------------------------------------------------------------------
// Sources panel
// ----------------------------------------------------------------------------
async function refreshSources({ showLoading = true } = {}) {
  if (showLoading) { state.sourcesLoading = true; renderSources(); }
  try {
    const res = await api.listSources();
    state.sources = res.sources || [];
    state.sourcesError = null;
  } catch (err) {
    state.sourcesError = friendlyError(err);
  } finally {
    state.sourcesLoading = false;
    renderSources();
  }
}

function renderSources() {
  const list = $("#source-list");
  list.replaceChildren();
  $("#source-count").textContent = state.sources.length ? `(${state.sources.length})` : "";

  if (state.sourcesLoading) {
    list.append(h("li", { class: "skeleton" }), h("li", { class: "skeleton" }), h("li", { class: "skeleton" }));
  } else if (state.sourcesError) {
    list.append(h("li", { class: "empty-state" },
      h("span", { class: "big" }, "⚠️"),
      h("div", {}, state.sourcesError),
      h("button", { class: "btn small", style: "margin-top:8px", onclick: () => refreshSources() }, "Retry"),
    ));
  } else if (state.sources.length === 0) {
    list.append(h("li", { class: "empty-state" },
      h("span", { class: "big" }, "📚"),
      "No sources yet. Add a document, web page or Wikipedia article to get started.",
    ));
  } else {
    for (const source of state.sources) {
      const meta = typeMeta(source.type);
      list.append(h("li", { class: "source-item" },
        h("span", { class: "source-icon", "aria-hidden": "true" }, meta.icon),
        h("div", { class: "source-body" },
          h("div", { class: "source-name", title: source.source }, source.source),
          h("div", { class: "source-meta" },
            h("span", { class: "badge neutral" }, meta.label),
            `${source.chunk_count} chunk${source.chunk_count === 1 ? "" : "s"}`),
        ),
        h("button", {
          class: "icon-btn danger", title: "Delete source",
          "aria-label": `Delete ${source.source}`, onclick: () => confirmDelete(source),
        }, "🗑"),
      ));
    }
  }
  updateComposer();
}

function confirmDelete(source) {
  const dialog = $("#confirm-dialog");
  $("#confirm-text").textContent =
    `“${source.source}” and its ${source.chunk_count} chunks will be removed from the knowledge base.`;
  dialog.returnValue = "";
  dialog.addEventListener("close", async () => {
    if (dialog.returnValue !== "confirm") return;
    try {
      const res = await api.deleteSource(source.source_id);
      state.sources = res.sources || [];
      toast("Source deleted", "success");
      renderSources();
    } catch (err) {
      toast(friendlyError(err), "error");
      if (err.status === 404) refreshSources({ showLoading: false });
    }
  }, { once: true });
  dialog.showModal();
}

/** One place that turns an IngestResult into user feedback. */
function handleIngestResult(res) {
  if (res.status === "already_exists") {
    toast("Already in your knowledge base", "info");
  } else if (res.cache_synced === false) {
    toast(res.message || "Added, but cached answers may be outdated.", "warning", 7000);
  } else {
    const base = `Added ${res.chunks_added} chunk${res.chunks_added === 1 ? "" : "s"}`;
    toast(res.message ? `${base}. ${res.message}` : base, "success");
  }
}

// ---- Upload queue -----------------------------------------------------------
function precheck(file) {
  const ext = extOf(file.name);
  if (!ALLOWED_EXTENSIONS.includes(ext)) return `Unsupported file type (${ext || "no extension"})`;
  if (file.size === 0) return "The file is empty";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `Larger than ${MAX_UPLOAD_MB} MB`;
  return null;
}

function addFiles(fileList) {
  for (const file of fileList) {
    const item = { id: nextUploadId++, name: file.name, file, status: "queued", text: "Waiting…" };
    const problem = precheck(file);
    if (problem) { item.status = "failed"; item.text = problem; item.file = null; }
    state.uploads.push(item);
  }
  renderQueue();
  processQueue();
}

async function processQueue() {
  if (state.processing) return;
  state.processing = true;
  try {
    let item;
    while ((item = state.uploads.find((u) => u.status === "queued"))) {
      item.status = "uploading";
      item.text = extOf(item.name) === ".wav"
        ? "Transcribing… audio files can take a few minutes"
        : "Processing…";
      renderQueue();
      try {
        const res = await api.uploadFile(item.file);
        item.status = res.status === "already_exists" ? "exists" : "done";
        item.text = res.status === "already_exists" ? "Already added" : `Added ${res.chunks_added} chunks`;
        item.file = null;                                  // free the memory
        handleIngestResult(res);
        await refreshSources({ showLoading: false });
      } catch (err) {
        item.status = "failed";
        item.text = friendlyError(err);                    // the file is kept so Retry works
      }
      renderQueue();
    }
  } finally {
    state.processing = false;
  }
}

function renderQueue() {
  const list = $("#upload-queue");
  list.replaceChildren();
  for (const item of state.uploads) {
    const icon = {
      queued: "⏳", uploading: h("span", { class: "spinner", "aria-label": "Uploading" }),
      done: "✅", exists: "ℹ️", failed: "❌",
    }[item.status];
    const busy = item.status === "queued" || item.status === "uploading";
    list.append(h("li", { class: `queue-item ${item.status === "exists" ? "done" : item.status}` },
      h("span", { "aria-hidden": "true" }, icon),
      h("div", { style: "min-width:0" },
        h("div", { class: "queue-name", title: item.name }, item.name),
        h("div", { class: "queue-text" }, item.text)),
      h("div", { class: "queue-actions" },
        item.status === "failed" && item.file
          ? h("button", {
              class: "icon-btn small", title: "Retry", "aria-label": `Retry ${item.name}`,
              onclick: () => { item.status = "queued"; item.text = "Waiting…"; renderQueue(); processQueue(); },
            }, "↻")
          : null,
        !busy
          ? h("button", {
              class: "icon-btn small", title: "Remove", "aria-label": `Remove ${item.name} from the list`,
              onclick: () => { state.uploads = state.uploads.filter((u) => u !== item); renderQueue(); },
            }, "✕")
          : null),
    ));
  }
  $("#btn-clear-finished").hidden = !state.uploads.some((u) => !["queued", "uploading"].includes(u.status));
}

function initUpload() {
  const zone = $("#dropzone");
  const input = $("#file-input");
  $("#accept-hint").textContent =
    `PDF, DOCX, TXT, PPT/PPTX, WAV and source code · up to ${MAX_UPLOAD_MB} MB`;

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
  });
  input.addEventListener("change", () => { addFiles([...input.files]); input.value = ""; });

  for (const type of ["dragenter", "dragover"]) {
    zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  }
  for (const type of ["dragleave", "drop"]) {
    zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.remove("dragover"); });
  }
  zone.addEventListener("drop", (e) => addFiles([...e.dataTransfer.files]));

  $("#btn-clear-finished").addEventListener("click", () => {
    state.uploads = state.uploads.filter((u) => ["queued", "uploading"].includes(u.status));
    renderQueue();
  });
  $("#btn-refresh").addEventListener("click", () => refreshSources());
}

// ---- URL and Wikipedia forms -----------------------------------------------
async function runIngest(form, action, onSuccess) {
  const controls = [...form.elements];
  const button = form.querySelector("button[type=submit]");
  const label = button.textContent;
  controls.forEach((c) => (c.disabled = true));
  button.textContent = "Adding…";
  try {
    const res = await action();
    handleIngestResult(res);
    onSuccess?.();
    await refreshSources({ showLoading: false });
  } catch (err) {
    toast(friendlyError(err), "error", 6500);
  } finally {
    controls.forEach((c) => (c.disabled = false));
    button.textContent = label;
  }
}

function initForms() {
  $("#url-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#url-input");
    const url = input.value.trim();
    if (!/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(url)) {
      showFieldError("#url-error", "Enter a full URL starting with http:// or https://");
      return;
    }
    showFieldError("#url-error", "");
    runIngest(e.currentTarget, () => api.addUrl(url), () => { input.value = ""; });
  });

  const lang = $("#wiki-lang");
  for (const code of WIKI_LANGS) lang.append(h("option", { value: code }, code));
  $("#wiki-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#wiki-input");
    const page = input.value.trim();
    if (!page) { showFieldError("#wiki-error", "Enter a page title or URL"); return; }
    showFieldError("#wiki-error", "");
    runIngest(e.currentTarget, () => api.addWikipedia(page, lang.value), () => { input.value = ""; });
  });
}

// ----------------------------------------------------------------------------
// Chat
// ----------------------------------------------------------------------------
const messagesKey = () => `chat_messages:${state.sessionId}`;

function loadSession() {
  state.sessionId = lsGet("session_id");
  if (!state.sessionId) { state.sessionId = uid(); lsSet("session_id", state.sessionId); }
  try {
    state.messages = JSON.parse(lsGet(messagesKey()) || "[]").filter((m) => m.status !== "pending");
  } catch { state.messages = []; }
}

function saveMessages() {
  const saved = state.messages.filter((m) => m.status !== "pending").slice(-100);
  lsSet(messagesKey(), JSON.stringify(saved));
}

function newChat() {
  state.chatAbort?.abort();
  state.sending = false;
  state.sessionId = uid();
  lsSet("session_id", state.sessionId);
  state.messages = [];
  renderMessages();
  updateComposer();
  $("#question").focus();
}

async function ask(question, replaceId = null) {
  if (state.sending || !question.trim()) return;
  const sessionAtStart = state.sessionId;

  const pending = { id: uid(), role: "assistant", status: "pending", question };
  if (replaceId) {
    const index = state.messages.findIndex((m) => m.id === replaceId);
    if (index >= 0) state.messages[index] = pending; else state.messages.push(pending);
  } else {
    state.messages.push({ id: uid(), role: "user", content: question }, pending);
  }
  state.sending = true;
  state.chatAbort = new AbortController();
  renderMessages();
  updateComposer();

  try {
    pending.data = await api.chat({ question, session_id: sessionAtStart }, state.chatAbort.signal);
    pending.status = "done";
  } catch (err) {
    if (err?.name === "AbortError") return;                 // "New chat" cancelled this request
    pending.status = "error";
    pending.error = friendlyError(err);
  } finally {
    if (state.sessionId === sessionAtStart) {
      state.sending = false;
      saveMessages();
      renderMessages();
      updateComposer();
    }
  }
}

function badge(kind, text, title) {
  return h("span", { class: `badge ${kind}`, title }, text);
}

function iterationDots(used) {
  const dots = h("span", { class: "iter-dots", "aria-hidden": "true" });
  for (let i = 1; i <= MAX_ITERATIONS; i++) dots.append(h("span", { class: i <= used ? "on" : "" }));
  return dots;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Answer copied", "success", 2000);
  } catch {
    toast("Could not copy automatically", "error");
  }
}

function assistantCard(msg) {
  if (msg.status === "pending") {
    return h("div", { class: "card-answer" },
      h("div", { class: "typing" },
        h("span", { class: "typing-dots", "aria-hidden": "true" }, h("span"), h("span"), h("span")),
        h("span", {}, "Generating and reviewing the answer… this can take up to a minute")));
  }

  if (msg.status === "error") {
    return h("div", { class: "card-answer error", role: "alert" },
      h("p", { class: "error-text" }, msg.error),
      h("button", { class: "btn small", onclick: () => ask(msg.question, msg.id) }, "Retry"));
  }

  const d = msg.data;
  const badges = [];
  if (d.insufficient_knowledge) badges.push(badge("info", "Not found in your sources"));
  else if (d.validated) badges.push(badge("success", "✓ Validated by evaluator"));
  else badges.push(badge("warning", "⚠ Not fully validated"));

  if (d.iterations_used === 0 && d.cache_hit) {
    badges.push(badge("neutral", "Served from cache"));
  } else {
    if (d.iterations_used > 0) {
      const rounds = h("span", { class: "badge neutral", title: `${d.iterations_used} of ${MAX_ITERATIONS} review rounds` },
        `Reviewed in ${d.iterations_used} round${d.iterations_used === 1 ? "" : "s"}`, iterationDots(d.iterations_used));
      badges.push(rounds);
    }
    if (d.cache_hit) badges.push(badge("neutral", "Cached"));
  }

  const card = h("div", { class: "card-answer" },
    h("div", { class: "answer-top" },
      h("button", { class: "btn ghost small", onclick: () => copyText(d.answer) }, "Copy")),
    h("div", { class: "md", html: renderMarkdown(d.answer) }),
    h("div", { class: "answer-badges" }, badges),
  );

  if (!d.validated && !d.insufficient_knowledge) {
    card.append(h("div", { class: "note", role: "note" },
      `This answer could not be fully validated after ${MAX_ITERATIONS} review iterations. Please double-check it against your sources.`));
  }

  if (d.evaluator_feedback && d.evaluator_feedback.trim()) {
    card.append(h("details", {},
      h("summary", {}, "Evaluator feedback"),
      h("div", { class: "details-body" }, d.evaluator_feedback)));
  }

  if (Array.isArray(d.sources) && d.sources.length) {
    const body = h("div", { class: "details-body" });
    for (const ref of d.sources) {
      const meta = typeMeta(ref.type);
      body.append(h("div", { class: "ref" },
        h("div", { class: "ref-head" },
          h("span", { "aria-hidden": "true" }, meta.icon),
          h("span", { style: "overflow-wrap:anywhere" }, ref.source),
          ref.location ? h("span", { class: "badge neutral" }, ref.location) : null),
        ref.snippet ? h("blockquote", {}, ref.snippet) : null));
    }
    card.append(h("details", {}, h("summary", {}, `Sources (${d.sources.length})`), body));
  }
  return card;
}

function renderMessages() {
  const box = $("#messages");
  box.replaceChildren();

  if (state.messages.length === 0) {
    const chips = ["Summarize my sources", "What are the key points?", "List the main topics covered"];
    box.append(h("div", { class: "welcome" },
      h("h2", {}, "Ask anything about your sources"),
      h("p", {}, "Answers are generated from your knowledge base, then reviewed by an evaluator before you see them."),
      h("div", { class: "chips" },
        chips.map((text) => h("button", {
          class: "chip", type: "button",
          onclick: () => { const q = $("#question"); q.value = text; q.focus(); autosize(); updateComposer(); },
        }, text)))));
    return;
  }

  for (const msg of state.messages) {
    if (msg.role === "user") {
      box.append(h("div", { class: "msg-user" }, h("div", { class: "bubble-user" }, msg.content)));
    } else {
      box.append(assistantCard(msg));
    }
  }
  box.scrollTop = box.scrollHeight;
}

function autosize() {
  const q = $("#question");
  q.style.height = "auto";
  q.style.height = Math.min(q.scrollHeight, 180) + "px";
}

function updateComposer() {
  const q = $("#question");
  const noSources = !state.sourcesLoading && state.sources.length === 0;
  const empty = q.value.trim().length === 0;

  q.disabled = noSources;
  $("#btn-send").disabled = noSources || state.sending || empty;
  $("#composer-hint").textContent = noSources ? "Add at least one source to start asking questions" : "";

  const len = q.value.length;
  $("#char-count").textContent = len > MAX_QUESTION_LENGTH * 0.85 ? `${len}/${MAX_QUESTION_LENGTH}` : "";
}

function initChat() {
  const q = $("#question");
  q.maxLength = MAX_QUESTION_LENGTH;
  q.addEventListener("input", () => { autosize(); updateComposer(); });
  q.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("#composer").requestSubmit();
    }
  });
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = q.value.trim();
    if (!text || state.sending || q.disabled) return;
    q.value = "";
    autosize();
    updateComposer();
    ask(text);
  });
}

// ----------------------------------------------------------------------------
// Boot
// ----------------------------------------------------------------------------
function init() {
  initChrome();
  initUpload();
  initForms();
  initChat();
  loadSession();
  renderMessages();
  renderSources();
  updateComposer();
  refreshSources();
  pollHealth();
  setInterval(pollHealth, HEALTH_POLL_MS);
}

init();