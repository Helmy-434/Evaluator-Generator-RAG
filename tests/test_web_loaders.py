
import pytest

from langchain_core.documents import Document

from app.contract import SOURCE, TYPE, LOCATION, SourceType
from app.core.errors import InvalidRequest
from app.ingestion import web_loaders


@pytest.fixture
def sample_documents():
    return [
        Document(
            page_content="This is sample web content.",
            metadata={"title": "Example"},
        )
    ]


# Web loader tests

def test_load_web_page_success(monkeypatch, sample_documents):
    url = "https://example.com"

    monkeypatch.setattr(
        web_loaders,
        "validate_url",
        lambda value: value,
    )

    class MockWebBaseLoader:
        def __init__(self, **kwargs):
            assert kwargs["web_paths"] == (url,)

        def load(self):
            return sample_documents

    monkeypatch.setattr(
        web_loaders,
        "WebBaseLoader",
        MockWebBaseLoader,
    )

    documents = web_loaders.load_web_page(url)

    assert len(documents) == 1
    assert documents[0].page_content == "This is sample web content."
    assert documents[0].metadata[SOURCE] == url
    assert documents[0].metadata[TYPE] == SourceType.WEB.value
    assert documents[0].metadata[LOCATION] == ""


def test_load_web_page_validates_url(monkeypatch):
    def mock_validate_url(url):
        raise InvalidRequest("Invalid URL")

    monkeypatch.setattr(
        web_loaders,
        "validate_url",
        mock_validate_url,
    )

    with pytest.raises(InvalidRequest, match="Invalid URL"):
        web_loaders.load_web_page("http://localhost")


def test_load_web_page_empty_content(monkeypatch):
    monkeypatch.setattr(
        web_loaders,
        "validate_url",
        lambda value: value,
    )

    class MockWebBaseLoader:
        def __init__(self, **kwargs):
            pass

        def load(self):
            return [
                Document(
                    page_content="   ",
                    metadata={},
                )
            ]

    monkeypatch.setattr(
        web_loaders,
        "WebBaseLoader",
        MockWebBaseLoader,
    )

    with pytest.raises(InvalidRequest, match="No readable content"):
        web_loaders.load_web_page("https://example.com")


def test_load_web_page_loader_failure(monkeypatch):
    monkeypatch.setattr(
        web_loaders,
        "validate_url",
        lambda value: value,
    )

    class MockWebBaseLoader:
        def __init__(self, **kwargs):
            pass

        def load(self):
            raise RuntimeError("Connection failed")

    monkeypatch.setattr(
        web_loaders,
        "WebBaseLoader",
        MockWebBaseLoader,
    )

    with pytest.raises(InvalidRequest, match="Failed to load web page"):
        web_loaders.load_web_page("https://example.com")


# Wikipedia loader tests

def test_load_wikipedia_page_success(monkeypatch, sample_documents):
    page = "Python programming"
    source = "https://en.wikipedia.org/wiki/Python"

    sample_documents[0].metadata["source"] = source

    class MockWikipediaLoader:
        def __init__(self, **kwargs):
            assert kwargs["query"] == page
            assert kwargs["lang"] == "en"
            assert kwargs["load_max_docs"] == 1

        def load(self):
            return sample_documents

    monkeypatch.setattr(
        web_loaders,
        "WikipediaLoader",
        MockWikipediaLoader,
    )

    documents = web_loaders.load_wikipedia_page(page)

    assert len(documents) == 1
    assert documents[0].metadata[SOURCE] == source
    assert documents[0].metadata[TYPE] == SourceType.WIKIPEDIA.value
    assert documents[0].metadata[LOCATION] == ""


@pytest.mark.parametrize("page", ["", "   ", None])
def test_load_wikipedia_page_invalid_title(page):
    with pytest.raises(InvalidRequest, match="Wikipedia page title"):
        web_loaders.load_wikipedia_page(page)


def test_load_wikipedia_page_not_found(monkeypatch):
    class MockWikipediaLoader:
        def __init__(self, **kwargs):
            pass

        def load(self):
            return []

    monkeypatch.setattr(
        web_loaders,
        "WikipediaLoader",
        MockWikipediaLoader,
    )

    with pytest.raises(InvalidRequest, match="No Wikipedia page found"):
        web_loaders.load_wikipedia_page("Unknown page")


def test_load_wikipedia_page_loader_failure(monkeypatch):
    class MockWikipediaLoader:
        def __init__(self, **kwargs):
            pass

        def load(self):
            raise RuntimeError("Wikipedia unavailable")

    monkeypatch.setattr(
        web_loaders,
        "WikipediaLoader",
        MockWikipediaLoader,
    )

    with pytest.raises(InvalidRequest, match="Failed to load Wikipedia page"):
        web_loaders.load_wikipedia_page("Python programming")
