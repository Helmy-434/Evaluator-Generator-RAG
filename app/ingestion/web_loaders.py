from langchain_community.document_loaders import WebBaseLoader ,WikipediaLoader

from langchain_core.documents import Document

from app.core.contract import (
    SOURCE,
    TYPE,
    LOCATION,
    SourceType,
)
from app.ingestion.validators import validate_url
from app.core.errors import InvalidRequest


def _set_metadata(documents: list[Document], source: str, source_type: SourceType) -> list[Document]:

    for document in documents:
        document.metadata[SOURCE] = source
        document.metadata[TYPE] = source_type.value
        document.metadata[LOCATION] = (
            str(document.metadata.get(LOCATION) or "")
        )

    return documents


def load_web_page(url: str) -> list[Document]:

    url = validate_url(url)

    try:
        loader = WebBaseLoader(
            web_paths=(url,),
            requests_kwargs={
                "timeout": 15,
                "headers": {
                    "User-Agent": "RAGKnowledgeBase/1.0"
                },
            },
        )

        documents = loader.load()

        if not documents or not any(
            document.page_content.strip()
            for document in documents
        ):
            raise InvalidRequest("No readable content found at URL")

        return _set_metadata(
            documents,
            source=url,
            source_type=SourceType.WEB,
        )

    except InvalidRequest:
        raise
    except Exception as e:
        raise InvalidRequest(
            f"Failed to load web page: {e}"
        ) from e




def load_wikipedia_page(page: str, lang: str = "en") -> list[Document]:

    if not page or not page.strip():
        raise InvalidRequest("Wikipedia page title is required")

    try:
        loader = WikipediaLoader(
            query=page.strip(),
            lang=lang,
            load_max_docs=1,
        )

        documents = loader.load()

        if not documents:
            raise InvalidRequest(
                f"No Wikipedia page found for: {page}"
            )

        source = documents[0].metadata.get("source", page)

        return _set_metadata(
            documents,
            source=source,
            source_type=SourceType.WIKIPEDIA,
        )

    except InvalidRequest:
        raise
    except Exception as e:
        raise InvalidRequest(
            f"Failed to load Wikipedia page: {e}"
        ) from e