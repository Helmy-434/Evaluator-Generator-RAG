import pytest
from langchain_core.documents import Document

from app.contract import (
    CHUNK_ID,
    SOURCE_ID,
    SOURCE,
    TYPE,
    LOCATION,
    SourceType,
)
from app.core.config import settings
from app.ingestion.chunking import split_documents


@pytest.fixture
def sample_documents():
    return [
        Document(
            page_content="This is the first paragraph. " * 20,
            metadata={
                SOURCE: "document.pdf",
                TYPE: SourceType.PDF.value,
                LOCATION: "page 1",
            },
        ),
        Document(
            page_content="This is the second paragraph. " * 20,
            metadata={
                SOURCE: "document.pdf",
                TYPE: SourceType.PDF.value,
                LOCATION: "page 2",
            },
        ),
    ]


def test_split_documents_success(sample_documents):
    chunks = split_documents(sample_documents, "source123")

    assert len(chunks) > 1

    for index, chunk in enumerate(chunks):
        assert chunk.metadata[SOURCE_ID] == "source123"
        assert chunk.metadata[CHUNK_ID] == f"source123:{index}"
        assert chunk.metadata["chunk_index"] == index


def test_split_documents_preserves_metadata(sample_documents):
    chunks = split_documents(sample_documents, "source123")

    assert all(
        chunk.metadata[SOURCE] == "document.pdf"
        for chunk in chunks
    )
    assert all(
        chunk.metadata[TYPE] == SourceType.PDF.value
        for chunk in chunks
    )
    assert all(LOCATION in chunk.metadata for chunk in chunks)


def test_split_documents_empty_input():
    assert split_documents([], "source123") == []


def test_split_documents_missing_source_id(sample_documents):
    with pytest.raises(ValueError, match="source_id is required"):
        split_documents(sample_documents, "")


def test_split_documents_respects_chunk_size(sample_documents, monkeypatch):
    monkeypatch.setattr(settings, "chunk_size", 100)
    monkeypatch.setattr(settings, "chunk_overlap", 20)

    chunks = split_documents(sample_documents, "source123")

    assert all(len(chunk.page_content) <= 100 for chunk in chunks)


def test_split_documents_does_not_modify_original(sample_documents):
    original_content = sample_documents[0].page_content
    original_metadata = sample_documents[0].metadata.copy()

    split_documents(sample_documents, "source123")

    assert sample_documents[0].page_content == original_content
    assert sample_documents[0].metadata == original_metadata
