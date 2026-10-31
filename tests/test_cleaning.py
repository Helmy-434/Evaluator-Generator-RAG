
import pytest
from langchain_core.documents import Document

from app.contract import SOURCE, TYPE, LOCATION, SourceType
from app.ingestion.cleaning import clean_text, clean_documents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  Hello world  ", "Hello world"),
        ("Hello    world", "Hello world"),
        ("Hello\n\n\n\nworld", "Hello\n\nworld"),
        ("Hello\x00world", "Helloworld"),
        ("Hello\t\tworld", "Hello world"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_clean_text(text, expected):
    assert clean_text(text) == expected


def test_clean_documents_success():
    documents = [
        Document(
            page_content="  Hello    world  ",
            metadata={
                SOURCE: "document.pdf",
                TYPE: SourceType.PDF.value,
                LOCATION: "page 1",
            },
        )
    ]

    cleaned = clean_documents(documents)

    assert len(cleaned) == 1
    assert cleaned[0].page_content == "Hello world"
    assert cleaned[0].metadata[SOURCE] == "document.pdf"
    assert cleaned[0].metadata[TYPE] == SourceType.PDF.value
    assert cleaned[0].metadata[LOCATION] == "page 1"


def test_clean_documents_removes_empty_documents():
    documents = [
        Document(page_content="   ", metadata={}),
        Document(page_content="\x00", metadata={}),
        Document(page_content="Valid content", metadata={}),
    ]

    cleaned = clean_documents(documents)

    assert len(cleaned) == 1
    assert cleaned[0].page_content == "Valid content"


def test_clean_documents_does_not_modify_original():
    original = Document(
        page_content="  Hello    world  ",
        metadata={"source": "document.pdf"},
    )

    clean_documents([original])

    assert original.page_content == "  Hello    world  "
