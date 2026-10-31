// API client. `api` is either the real client or the mock client (same functions).
import {
  API_BASE_URL, USE_MOCK, REQUEST_TIMEOUT_MS, UPLOAD_TIMEOUT_MS, CHAT_TIMEOUT_MS, CODE_EXTENSIONS,
} from "./config.js";

export class ApiError extends Error {
  constructor(status, error, detail) {
    super(detail);
    this.name = "ApiError";
    this.status = status;   // HTTP status, 0 = no response (network / timeout)
    this.error = error;     // error code from the backend, e.g. "unsupported_file_type"
    this.detail = detail;   // human-readable message
  }
}

// ----------------------------------------------------------------------------
// Real client
// ----------------------------------------------------------------------------
async function request(path, { method = "GET", json, formData, timeout = REQUEST_TIMEOUT_MS, signal } = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let res;
  try {
    res = await fetch(`${API_BASE_URL}/api${path}`, {
      method,
      headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: json !== undefined ? JSON.stringify(json) : formData,
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) throw new ApiError(0, "timeout", "The request took too long and was cancelled.");
    if (controller.signal.aborted) throw new DOMException("Aborted", "AbortError");
    throw new ApiError(0, "network_error",
      "Cannot reach the backend. Check that it is running and that CORS allows this page's origin.");
  } finally {
    clearTimeout(timer);
  }

  let body = null;
  try { body = await res.json(); } catch { /* empty or non-JSON body */ }
  if (!res.ok) {
    throw new ApiError(res.status, body?.error || "http_error", body?.detail || `Request failed (${res.status})`);
  }
  return body;
}

const realApi = {
  health: () => request("/health", { timeout: 8000 }),
  listSources: () => request("/sources"),
  uploadFile: (file) => {
    const form = new FormData();
    form.append("file", file);                       // field name must be exactly "file"
    return request("/sources/files", { method: "POST", formData: form, timeout: UPLOAD_TIMEOUT_MS });
  },
  addUrl: (url) => request("/sources/url", { method: "POST", json: { url }, timeout: UPLOAD_TIMEOUT_MS }),
  addWikipedia: (page, lang) =>
    request("/sources/wikipedia", { method: "POST", json: { page, lang }, timeout: UPLOAD_TIMEOUT_MS }),
  deleteSource: (id) => request(`/sources/${encodeURIComponent(id)}`, { method: "DELETE" }),
  chat: (payload, signal) =>
    request("/chat", { method: "POST", json: payload, timeout: CHAT_TIMEOUT_MS, signal }),
};

// ----------------------------------------------------------------------------
// Mock client (?mock=1): same shapes as the backend, no server needed
// ----------------------------------------------------------------------------
const sleep = (min, max) => new Promise((r) => setTimeout(r, min + Math.random() * (max - min)));
const rid = () => Math.random().toString(36).slice(2, 12);
const extOf = (name) => { const i = name.lastIndexOf("."); return i >= 0 ? name.slice(i).toLowerCase() : ""; };

const mockSources = [
  { source_id: "m1", source: "company-handbook.pdf", type: "pdf", chunk_count: 42 },
  { source_id: "m2", source: "https://example.com/blog/rag-intro", type: "web", chunk_count: 11 },
  { source_id: "m3", source: "team-meeting.wav", type: "audio", chunk_count: 18 },
];

function mockTypeFor(name) {
  const ext = extOf(name);
  if (ext === ".pdf") return "pdf";
  if (ext === ".docx") return "docx";
  if (ext === ".txt") return "txt";
  if (ext === ".pptx" || ext === ".ppt") return "pptx";
  if (ext === ".wav") return "audio";
  if (CODE_EXTENSIONS.has(ext)) return "code";
  return null;
}

function ingestResult(src, status, extra = {}) {
  return {
    source_id: src.source_id, source: src.source, type: src.type, status,
    chunks_added: status === "ingested" ? src.chunk_count : 0,
    message: null, cache_synced: true, ...extra,
  };
}

const mockApi = {
  async health() { await sleep(100, 300); return { status: "ok", redis: true }; },

  async listSources() { await sleep(300, 700); return { sources: structuredClone(mockSources) }; },

  async uploadFile(file) {
    await sleep(800, 2200);
    const type = mockTypeFor(file.name);
    if (!type) throw new ApiError(415, "unsupported_file_type", `Unsupported file type: ${extOf(file.name) || "(none)"}`);
    if (file.name.toLowerCase().includes("fail")) {
      throw new ApiError(500, "ingestion_failed", `Could not index '${file.name}'. See the server log for details.`);
    }
    const existing = mockSources.find((s) => s.source === file.name);
    if (existing) {
      return ingestResult(existing, "already_exists", { message: "This file is already in the knowledge base." });
    }
    const src = { source_id: rid(), source: file.name, type, chunk_count: 5 + Math.floor(Math.random() * 55) };
    mockSources.push(src);
    return ingestResult(src, "ingested");
  },

  async addUrl(url) {
    await sleep(800, 1800);
    const existing = mockSources.find((s) => s.source === url);
    if (existing) {
      existing.chunk_count = 5 + Math.floor(Math.random() * 20);
      return ingestResult(existing, "ingested", { message: "Source refreshed: the previous version was replaced." });
    }
    const src = { source_id: rid(), source: url, type: "web", chunk_count: 4 + Math.floor(Math.random() * 25) };
    mockSources.push(src);
    return ingestResult(src, "ingested");
  },

  async addWikipedia(page, lang) {
    await sleep(800, 1800);
    const name = `Wikipedia: ${page}${lang !== "en" ? ` (${lang})` : ""}`;
    const existing = mockSources.find((s) => s.source === name);
    if (existing) return ingestResult(existing, "ingested", { message: "Source refreshed: the previous version was replaced." });
    const src = { source_id: rid(), source: name, type: "wikipedia", chunk_count: 8 + Math.floor(Math.random() * 40) };
    mockSources.push(src);
    return ingestResult(src, "ingested");
  },

  async deleteSource(id) {
    await sleep(300, 800);
    const i = mockSources.findIndex((s) => s.source_id === id);
    if (i < 0) throw new ApiError(404, "source_not_found", `No source with id ${id}`);
    mockSources.splice(i, 1);
    return { sources: structuredClone(mockSources) };
  },

  async chat({ question }, signal) {
    await sleep(1500, 3000);
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    if (mockSources.length === 0) {
      throw new ApiError(409, "no_knowledge_loaded", "No knowledge sources are loaded.");
    }
    const q = question.toLowerCase();
    const refs = [
      { source: "company-handbook.pdf", type: "pdf", location: "page 3",
        snippet: "Employees are entitled to 21 days of paid annual leave, which accrue monthly." },
      { source: "https://example.com/blog/rag-intro", type: "web", location: null,
        snippet: "Retrieval-augmented generation grounds a language model's answers in retrieved documents." },
    ];
    if (q.includes("error")) throw new ApiError(500, "internal_error", "Unexpected server error");
    if (q.includes("unvalidated")) {
      return {
        answer: "Based on the handbook, annual leave is **21 days**. The evaluator still found the carry-over rule unclear.",
        validated: false, iterations_used: 4, insufficient_knowledge: false, sources: refs,
        evaluator_feedback: "The carry-over policy is mentioned but not supported by a quoted passage.", cache_hit: false,
      };
    }
    if (q.includes("unknown")) {
      return {
        answer: "The required information is not available in the provided sources.",
        validated: true, iterations_used: 0, insufficient_knowledge: true, sources: [],
        evaluator_feedback: null, cache_hit: false,
      };
    }
    if (q.includes("cached")) {
      return {
        answer: "Annual leave is **21 days** per year (served from cache).",
        validated: true, iterations_used: 0, insufficient_knowledge: false, sources: refs,
        evaluator_feedback: null, cache_hit: true,
      };
    }
    return {
      answer:
        "Employees get **21 days** of paid annual leave per year.\n\n" +
        "- Leave accrues monthly.\n- Requests go through your manager.\n- Unused days partially carry over.\n\n" +
        "See the handbook for the full policy.",
      validated: true, iterations_used: 2, insufficient_knowledge: false, sources: refs,
      evaluator_feedback: "First draft missed the carry-over rule; the second iteration added it with a supporting source.",
      cache_hit: false,
    };
  },
};

export const api = USE_MOCK ? mockApi : realApi;