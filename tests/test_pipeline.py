
import hashlib

import pytest
from langchain_core.documents import Document

from app.contract import SOURCE, SOURCE_ID, CHUNK_ID, SourceType
from app.core.errors import InvalidRequest
from app.ingestion import pipeline


@pytest.fixture
def sample_documents():
    return [
        Document(
            page_content="This is a sample document. " * 50,
            metadata={
                SOURCE: "document.pdf",
            },
        )
    ]


@pytest.fixture
def mock_vector_store(monkeypatch):
    class MockVectorStore:
        def __init__(self):
            self.added_documents = []
            self.added_ids = []

        def add_documents(self, documents, ids):
            self.added_documents.extend(documents)
            self.added_ids.extend(ids)

    store = MockVectorStore()

    def add_chunks(chunks):
        store.add_documents(
            chunks,
            [chunk.metadata[CHUNK_ID] for chunk in chunks],
        )
        return len(chunks), pipeline.bump_corpus_version(pipeline.redis_client)

    monkeypatch.setattr(
        pipeline,
        "get_vector_store",
        lambda: store,
    )
    monkeypatch.setattr(pipeline, "add_chunks", add_chunks)

    return store


@pytest.fixture
def mock_cache(monkeypatch):
    cache = {"values": {}}

    def get(content):
        key = pipeline.ingestion_cache.generate_key(content)
        return cache["values"].get(key)

    def set_value(content, value):
        key = pipeline.ingestion_cache.generate_key(content)
        cache["values"][key] = value
        return True

    def exists(content):
        key = pipeline.ingestion_cache.generate_key(content)
        return key in cache["values"]

    monkeypatch.setattr(
        pipeline.ingestion_cache,
        "get",
        get,
    )

    monkeypatch.setattr(
        pipeline.ingestion_cache,
        "set",
        set_value,
    )

    monkeypatch.setattr(
        pipeline.ingestion_cache,
        "exists",
        exists,
    )

    return cache


@pytest.fixture
def mock_corpus_version(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "bump_corpus_version",
        lambda redis_client: "1",
    )


def test_generate_source_id():
    content = b"sample file content"

    expected = hashlib.sha256(content).hexdigest()

    assert pipeline.generate_source_id(content) == expected


def test_ingest_file_success(
    monkeypatch,
    sample_documents,
    mock_vector_store,
    mock_cache,
    mock_corpus_version,
):
    filename = "document.pdf"
    data = b"sample PDF content"

    monkeypatch.setattr(
        pipeline,
        "load_file",
        lambda filename, data, source_type: sample_documents,
    )

    monkeypatch.setattr(
        pipeline,
        "source_exists",
        lambda source_id: False,
    )

    result = pipeline.ingest_file(filename, data)

    expected_id = pipeline.generate_source_id(data)
    cache_key = pipeline.ingestion_cache.generate_key(data)

    assert result.status == "ingested"
    assert result.source_id == expected_id
    assert result.source == filename
    assert result.type == SourceType.PDF
    assert result.chunks_added > 0
    assert result.cache_synced is True

    assert len(mock_vector_store.added_documents) > 0

    assert all(
        chunk.metadata[SOURCE_ID] == expected_id
        for chunk in mock_vector_store.added_documents
    )

    assert all(
        CHUNK_ID in chunk.metadata
        for chunk in mock_vector_store.added_documents
    )

    assert mock_cache["values"][cache_key] == expected_id


def test_ingest_file_already_in_cache(
    monkeypatch,
    mock_cache,
):
    data = b"sample PDF content"
    source_id = pipeline.generate_source_id(data)

    cache_key = pipeline.ingestion_cache.generate_key(data)
    mock_cache["values"][cache_key] = source_id

    monkeypatch.setattr(
        pipeline,
        "source_exists",
        lambda value: True,
    )

    def should_not_load(*args, **kwargs):
        pytest.fail("File loader should not be called")

    monkeypatch.setattr(
        pipeline,
        "load_file",
        should_not_load,
    )

    result = pipeline.ingest_file("document.pdf", data)

    assert result.status == "already_exists"
    assert result.source_id == source_id
    assert result.chunks_added == 0


def test_ingest_file_already_in_vector_store(
    monkeypatch,
    mock_cache,
):
    data = b"sample PDF content"
    source_id = pipeline.generate_source_id(data)

    monkeypatch.setattr(
        pipeline,
        "source_exists",
        lambda value: value == source_id,
    )

    result = pipeline.ingest_file("document.pdf", data)

    cache_key = pipeline.ingestion_cache.generate_key(data)

    assert result.status == "already_exists"
    assert result.source_id == source_id
    assert mock_cache["values"][cache_key] == source_id


def test_ingest_file_invalid_input():
    with pytest.raises(InvalidRequest):
        pipeline.ingest_file("", b"some content")


def test_ingest_file_empty_content():
    with pytest.raises(InvalidRequest):
        pipeline.ingest_file("document.pdf", b"")


def test_ingest_file_loader_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        pipeline,
        "source_exists",
        lambda source_id: False,
    )

    def raise_error(*args, **kwargs):
        raise RuntimeError("File loading failed")

    monkeypatch.setattr(
        pipeline,
        "load_file",
        raise_error,
    )

    with pytest.raises(RuntimeError, match="File loading failed"):
        pipeline.ingest_file("document.pdf", b"valid content")


def test_ingest_documents_empty_input():
    with pytest.raises(InvalidRequest, match="No readable content"):
        pipeline._ingest_documents(
            documents=[],
            source_id="source123",
            source="document.pdf",
            source_type=SourceType.PDF,
            cache_content=b"content",
        )


def test_ingest_documents_no_usable_content(
    mock_vector_store,
):
    documents = [
        Document(page_content="   ", metadata={})
    ]

    with pytest.raises(InvalidRequest, match="no usable text"):
        pipeline._ingest_documents(
            documents=documents,
            source_id="source123",
            source="document.pdf",
            source_type=SourceType.PDF,
            cache_content=b"content",
        )


def test_ingest_documents_corpus_version_failure(
    monkeypatch,
    sample_documents,
    mock_vector_store,
    mock_cache,
):
    monkeypatch.setattr(
        pipeline,
        "bump_corpus_version",
        lambda redis_client: None,
    )

    result = pipeline._ingest_documents(
        documents=sample_documents,
        source_id="source123",
        source="document.pdf",
        source_type=SourceType.PDF,
        cache_content=b"content",
    )

    assert result.status == "ingested"
    assert result.cache_synced is False
    assert len(mock_vector_store.added_documents) > 0


def test_ingest_documents_cache_failure(
    monkeypatch,
    sample_documents,
    mock_vector_store,
    mock_cache,
    mock_corpus_version,
):
    monkeypatch.setattr(
        pipeline.ingestion_cache,
        "set",
        lambda content, value: False,
    )

    result = pipeline._ingest_documents(
        documents=sample_documents,
        source_id="source123",
        source="document.pdf",
        source_type=SourceType.PDF,
        cache_content=b"content",
    )

    assert result.status == "ingested"
    assert result.cache_synced is False


def test_ingest_url_success(
    monkeypatch,
    sample_documents,
    mock_vector_store,
    mock_cache,
    mock_corpus_version,
):
    url = "https://example.com"

    monkeypatch.setattr(
        pipeline,
        "validate_url",
        lambda value: value,
    )

    monkeypatch.setattr(
        pipeline,
        "load_web_page",
        lambda value: sample_documents,
    )

    monkeypatch.setattr(
        pipeline,
        "source_exists",
        lambda source_id: False,
    )

    result = pipeline.ingest_url(url)

    assert result.status == "ingested"
    assert result.type == SourceType.WEB
    assert result.source == url
    assert result.chunks_added > 0


def test_ingest_wikipedia_success(
    monkeypatch,
    sample_documents,
    mock_vector_store,
    mock_cache,
    mock_corpus_version,
):
    page = "Python programming"

    sample_documents[0].metadata[SOURCE] = (
        "https://en.wikipedia.org/wiki/Python"
    )

    monkeypatch.setattr(
        pipeline,
        "load_wikipedia_page",
        lambda page, lang: sample_documents,
    )

    monkeypatch.setattr(
        pipeline,
        "source_exists",
        lambda source_id: False,
    )

    result = pipeline.ingest_wikipedia(page, "en")

    assert result.status == "ingested"
    assert result.type == SourceType.WIKIPEDIA
    assert result.source == "https://en.wikipedia.org/wiki/Python"
    assert result.chunks_added > 0