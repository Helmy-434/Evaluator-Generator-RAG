"""API tests for app/api/sources.py (and the error handlers in core/errors.py).

The pipeline and the vector store are replaced by fakes, so these tests need no Chroma, no
Redis and no OpenAI key. They check only what the API layer is responsible for: routing,
request checks, status codes and the ErrorResponse bodies.
"""
import sys
import types

# --- Let this file run before app/ingestion/pipeline.py exists ---------------------------------
# sources.py imports the pipeline at module level. If the real module is missing (not written
# yet), register an empty stand-in; every test replaces the functions with its own fakes anyway.
try:
    import app.ingestion.pipeline  # noqa: F401
except ImportError:
    if "app.ingestion" not in sys.modules:
        _pkg = types.ModuleType("app.ingestion")
        _pkg.__path__ = []  # mark it as a package
        sys.modules["app.ingestion"] = _pkg
    _stub = types.ModuleType("app.ingestion.pipeline")
    _stub.ingest_file = _stub.ingest_url = _stub.ingest_wikipedia = lambda *a, **k: None
    sys.modules["app.ingestion.pipeline"] = _stub

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import sources  # noqa: E402
from app.contract import IngestResult, SourceInfo, SourceType  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.errors import UnsupportedFileType  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    # raise_server_exceptions=False: an unexpected error must come back as an HTTP 500
    # response (that is what the real server does), not be re-raised inside the test.
    return TestClient(app, raise_server_exceptions=False)


def make_result(**overrides) -> IngestResult:
    data = dict(
        source_id="abc",
        source="a.txt",
        type=SourceType.TXT,
        status="ingested",
        chunks_added=3,
    )
    data.update(overrides)
    return IngestResult(**data)


# =============================================================================
# POST /api/sources/files
# =============================================================================
def test_upload_file_success(client, monkeypatch):
    calls = []

    def fake_ingest_file(filename, data):
        calls.append((filename, data))
        return make_result()

    monkeypatch.setattr(sources, "ingest_file", fake_ingest_file)

    r = client.post("/api/sources/files", files={"file": ("a.txt", b"hello", "text/plain")})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ingested"
    assert body["chunks_added"] == 3
    assert body["type"] == "txt"
    assert calls == [("a.txt", b"hello")]


def test_upload_file_already_exists_is_200(client, monkeypatch):
    monkeypatch.setattr(
        sources, "ingest_file",
        lambda f, d: make_result(status="already_exists", chunks_added=0),
    )
    r = client.post("/api/sources/files", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 200
    assert r.json()["status"] == "already_exists"


def test_upload_file_too_large(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    pipeline_called = []
    monkeypatch.setattr(sources, "ingest_file", lambda f, d: pipeline_called.append(1))

    too_big = b"x" * (1024 * 1024 + 1)
    r = client.post("/api/sources/files", files={"file": ("big.txt", too_big, "text/plain")})

    assert r.status_code == 413
    assert r.json()["error"] == "file_too_large"
    assert pipeline_called == []          # rejected before the pipeline ran


def test_upload_file_at_exact_limit_is_accepted(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    monkeypatch.setattr(sources, "ingest_file", lambda f, d: make_result())

    exactly = b"x" * (1024 * 1024)
    r = client.post("/api/sources/files", files={"file": ("ok.txt", exactly, "text/plain")})
    assert r.status_code == 200


def test_upload_without_file_is_validation_error(client):
    r = client.post("/api/sources/files")
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_upload_pipeline_validation_error_becomes_4xx(client, monkeypatch):
    def fake_ingest_file(filename, data):
        raise UnsupportedFileType("Unsupported file type: .exe")

    monkeypatch.setattr(sources, "ingest_file", fake_ingest_file)

    r = client.post("/api/sources/files", files={"file": ("virus.exe", b"MZ", "application/octet-stream")})

    assert r.status_code == 415
    assert r.json() == {"error": "unsupported_file_type", "detail": "Unsupported file type: .exe"}


def test_failed_result_becomes_500_ingestion_failed(client, monkeypatch):
    monkeypatch.setattr(
        sources, "ingest_file",
        lambda f, d: make_result(status="failed", chunks_added=0, message="Embedding API key invalid"),
    )
    r = client.post("/api/sources/files", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 500
    assert r.json() == {"error": "ingestion_failed", "detail": "Embedding API key invalid"}


def test_failed_result_without_message_uses_fallback(client, monkeypatch):
    monkeypatch.setattr(
        sources, "ingest_file",
        lambda f, d: make_result(status="failed", chunks_added=0, message=None),
    )
    r = client.post("/api/sources/files", files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 500
    assert r.json()["detail"] == "Ingestion failed"


def test_unexpected_error_is_500_and_does_not_leak_details(client, monkeypatch):
    def boom(filename, data):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(sources, "ingest_file", boom)

    r = client.post("/api/sources/files", files={"file": ("a.txt", b"hello", "text/plain")})

    assert r.status_code == 500
    assert r.json()["error"] == "internal_error"
    assert "secret internal detail" not in r.text


# =============================================================================
# POST /api/sources/url
# =============================================================================
def test_add_url_success_and_strips_whitespace(client, monkeypatch):
    seen = []

    def fake_ingest_url(url):
        seen.append(url)
        return make_result(source="https://example.com", type=SourceType.WEB)

    monkeypatch.setattr(sources, "ingest_url", fake_ingest_url)

    r = client.post("/api/sources/url", json={"url": "  https://example.com  "})

    assert r.status_code == 200
    assert r.json()["type"] == "web"
    assert seen == ["https://example.com"]


def test_add_url_empty_is_rejected(client, monkeypatch):
    called = []
    monkeypatch.setattr(sources, "ingest_url", lambda u: called.append(u))

    r = client.post("/api/sources/url", json={"url": "   "})

    assert r.status_code == 422
    assert r.json()["error"] == "invalid_url"
    assert called == []


def test_add_url_missing_field_is_validation_error(client):
    r = client.post("/api/sources/url", json={})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


# =============================================================================
# POST /api/sources/wikipedia
# =============================================================================
def test_add_wikipedia_success(client, monkeypatch):
    seen = []

    def fake_ingest_wikipedia(page, lang):
        seen.append((page, lang))
        return make_result(source="Alan Turing", type=SourceType.WIKIPEDIA)

    monkeypatch.setattr(sources, "ingest_wikipedia", fake_ingest_wikipedia)

    r = client.post("/api/sources/wikipedia", json={"page": " Alan Turing ", "lang": "en"})

    assert r.status_code == 200
    assert r.json()["type"] == "wikipedia"
    assert seen == [("Alan Turing", "en")]


def test_add_wikipedia_default_language_is_en(client, monkeypatch):
    seen = []
    monkeypatch.setattr(
        sources, "ingest_wikipedia",
        lambda page, lang: seen.append(lang) or make_result(type=SourceType.WIKIPEDIA),
    )
    client.post("/api/sources/wikipedia", json={"page": "Cairo"})
    assert seen == ["en"]


def test_add_wikipedia_empty_page_is_rejected(client):
    r = client.post("/api/sources/wikipedia", json={"page": "  "})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"


# =============================================================================
# GET /api/sources
# =============================================================================
def test_list_sources(client, monkeypatch):
    monkeypatch.setattr(
        sources, "list_sources",
        lambda: [SourceInfo(source_id="abc", source="a.pdf", type=SourceType.PDF, chunk_count=7)],
    )

    r = client.get("/api/sources")

    assert r.status_code == 200
    assert r.json() == {
        "sources": [{"source_id": "abc", "source": "a.pdf", "type": "pdf", "chunk_count": 7}]
    }


def test_list_sources_empty(client, monkeypatch):
    monkeypatch.setattr(sources, "list_sources", lambda: [])
    r = client.get("/api/sources")
    assert r.status_code == 200
    assert r.json() == {"sources": []}


# =============================================================================
# DELETE /api/sources/{source_id}
# =============================================================================
def test_delete_source_success_returns_updated_list(client, monkeypatch):
    deleted = []
    monkeypatch.setattr(sources, "source_exists", lambda sid: True)
    monkeypatch.setattr(sources, "delete_source", lambda sid: deleted.append(sid) or (3, "2"))
    monkeypatch.setattr(sources, "list_sources", lambda: [])

    r = client.delete("/api/sources/abc")

    assert r.status_code == 200
    assert r.json() == {"sources": []}
    assert deleted == ["abc"]


def test_delete_unknown_source_is_404(client, monkeypatch):
    deleted = []
    monkeypatch.setattr(sources, "source_exists", lambda sid: False)
    monkeypatch.setattr(sources, "delete_source", lambda sid: deleted.append(sid))

    r = client.delete("/api/sources/nope")

    assert r.status_code == 404
    assert r.json()["error"] == "source_not_found"
    assert deleted == []                  # nothing was deleted


# =============================================================================
# GET /api/health
# =============================================================================
@pytest.mark.parametrize("redis_up", [True, False])
def test_health_reports_redis_but_stays_ok(client, monkeypatch, redis_up):
    import app.main as main_module

    monkeypatch.setattr(main_module.redis_client, "ping", lambda: redis_up)

    r = client.get("/api/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "redis": redis_up}