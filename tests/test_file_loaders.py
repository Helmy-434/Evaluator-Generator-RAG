import pytest
from unittest.mock import patch

from langchain_core.documents import Document

from app.contract import (
    SourceType,
    SOURCE,
    TYPE,
    LOCATION,
)

from app.ingestion.file_loaders import (
    load_pdf,
    load_docx,
    load_txt,
    load_pptx,
    load_code,
    load_file,
)

from app.core.errors import IngestionFailed


@pytest.fixture
def sample_documents():
    return [
        Document(
            page_content="This is test content.",
            metadata={}
        )
    ]


def test_load_txt(sample_documents):
    content = b"This is a test text file."

    with patch(
        "app.ingestion.file_loaders.TextLoader.load",
        return_value=sample_documents
    ):
        documents = load_txt("example.txt", content)

    assert len(documents) == 1
    assert documents[0].page_content == "This is test content."
    assert documents[0].metadata[SOURCE] == "example.txt"
    assert documents[0].metadata[TYPE] == SourceType.TXT.value
    assert documents[0].metadata[LOCATION] == ""


def test_load_code(sample_documents):
    content = b"print('Hello World')"

    with patch(
        "app.ingestion.file_loaders.TextLoader.load",
        return_value=sample_documents
    ):
        documents = load_code("main.py", content)

    assert documents[0].metadata[SOURCE] == "main.py"
    assert documents[0].metadata[TYPE] == SourceType.CODE.value
    assert documents[0].metadata["language"] == "py"


def test_load_pdf(sample_documents):
    with patch(
        "app.ingestion.file_loaders.PyPDFLoader.load",
        return_value=sample_documents
    ):
        documents = load_pdf("document.pdf", b"fake pdf")

    assert documents[0].metadata[SOURCE] == "document.pdf"
    assert documents[0].metadata[TYPE] == SourceType.PDF.value
    assert documents[0].metadata[LOCATION] == ""


def test_load_docx(sample_documents):
    with patch(
        "app.ingestion.file_loaders.Docx2txtLoader.load",
        return_value=sample_documents
    ):
        documents = load_docx("document.docx", b"fake docx")

    assert documents[0].metadata[SOURCE] == "document.docx"
    assert documents[0].metadata[TYPE] == SourceType.DOCX.value


def test_load_pptx(sample_documents):
    with patch(
        "app.ingestion.file_loaders.UnstructuredPowerPointLoader.load",
        return_value=sample_documents
    ):
        documents = load_pptx("presentation.pptx", b"fake pptx")

    assert documents[0].metadata[SOURCE] == "presentation.pptx"
    assert documents[0].metadata[TYPE] == SourceType.PPTX.value


def test_load_file_dispatches_to_correct_loader(sample_documents):
    with patch(
        "app.ingestion.file_loaders.load_txt",
        return_value=sample_documents
    ) as mock_loader:

        documents = load_file(
            "example.txt",
            b"test content",
            SourceType.TXT
        )

    mock_loader.assert_called_once_with("example.txt", b"test content")
    assert documents == sample_documents


def test_load_file_rejects_unsupported_type():
    with pytest.raises(IngestionFailed):
        load_file(
            "audio.mp3",
            b"audio content",
            SourceType.AUDIO
        )


def test_load_file_removes_empty_documents():
    documents = [
        Document(page_content="Valid content", metadata={}),
        Document(page_content="   ", metadata={}),
        Document(page_content="", metadata={}),
    ]

    with patch(
        "app.ingestion.file_loaders.load_txt",
        return_value=documents
    ):
        result = load_file(
            "example.txt",
            b"content",
            SourceType.TXT
        )

    assert len(result) == 1
    assert result[0].page_content == "Valid content"


def test_load_file_fails_when_no_content():
    documents = [
        Document(page_content=" ", metadata={}),
        Document(page_content="", metadata={}),
    ]

    with patch(
        "app.ingestion.file_loaders.load_txt",
        return_value=documents
    ):
        with pytest.raises(IngestionFailed):
            load_file(
                "example.txt",
                b"content",
                SourceType.TXT
            )


def test_load_txt_handles_loader_error():
    with patch(
        "app.ingestion.file_loaders.TextLoader.load",
        side_effect=Exception("Invalid file")
    ):
        with pytest.raises(IngestionFailed):
            load_txt("broken.txt", b"invalid content")