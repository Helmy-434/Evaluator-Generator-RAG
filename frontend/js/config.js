// Frontend configuration: the single place to change URLs and limits.

function lsGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

const params = new URLSearchParams(window.location.search);

// Backend address. Override with ?api=http://host:8000 (it is remembered in localStorage).
if (params.get("api")) {
  try { localStorage.setItem("api_base_url", params.get("api")); } catch { /* ignore */ }
}
export const API_BASE_URL = (
  params.get("api") || lsGet("api_base_url") || "http://localhost:8000"
).replace(/\/+$/, "");

// Mock mode: no backend needed. Enable with ?mock=1 and disable with ?mock=0.
if (params.get("mock") === "1") {
  try { localStorage.setItem("use_mock", "1"); } catch { /* ignore */ }
}
if (params.get("mock") === "0") {
  try { localStorage.removeItem("use_mock"); } catch { /* ignore */ }
}
export const USE_MOCK = params.get("mock") === "1" || (params.get("mock") !== "0" && lsGet("use_mock") === "1");

// Limits. Keep ALLOWED_EXTENSIONS and MAX_UPLOAD_MB in sync with the backend
// (app/ingestion/validators.py and MAX_UPLOAD_MB in .env). The server stays the real authority.
export const MAX_UPLOAD_MB = 25;
export const ALLOWED_EXTENSIONS = [
  ".pdf", ".docx", ".txt", ".pptx", ".ppt", ".wav",
  // source code
  ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs",
  ".rb", ".php", ".sh", ".sql", ".html", ".css", ".json", ".yaml", ".yml", ".md",
];
export const CODE_EXTENSIONS = new Set([
  ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs",
  ".rb", ".php", ".sh", ".sql", ".html", ".css", ".json", ".yaml", ".yml", ".md",
]);

export const MAX_QUESTION_LENGTH = 4000;
export const MAX_ITERATIONS = 4;              // the evaluator loop cap
export const HEALTH_POLL_MS = 30_000;
export const REQUEST_TIMEOUT_MS = 30_000;     // list / delete / url / wikipedia / health
export const UPLOAD_TIMEOUT_MS = 10 * 60_000; // audio transcription can be slow
export const CHAT_TIMEOUT_MS = 3 * 60_000;

export const WIKI_LANGS = ["en", "ar", "fr", "de", "es", "it", "pt", "ru", "zh", "ja"];