
import logging
import tempfile

from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    TextLoader,
)

from app.contract import SourceType, SOURCE, TYPE, LOCATION
from app.core.errors import IngestionFailed


logger = logging.getLogger(__name__)


def _set_metadata(
    documents: list[Document],
    filename: str,
    source_type: SourceType,
) -> list[Document]:

    for document in documents:
        document.metadata[SOURCE] = filename
        document.metadata[TYPE] = source_type.value

        # Keep an existing location if the loader provides one.
        if LOCATION not in document.metadata:
            document.metadata[LOCATION] = ""

    return documents


def _load_with_tempfile(
    filename: str,
    data: bytes,
    suffix: str,
    loader_class,
    **loader_kwargs,
) -> list[Document]:

    with tempfile.NamedTemporaryFile(suffix=suffix) as file:
        file.write(data)
        file.flush()

        loader = loader_class(file.name, **loader_kwargs)
        return loader.load()



def load_pdf(filename: str, data: bytes) -> list[Document]:

    try:
        documents = _load_with_tempfile(
            filename,
            data,
            ".pdf",
            PyPDFLoader,
        )

        for document in documents:
            page = document.metadata.get("page")

            document.metadata[LOCATION] = (
                f"page {page + 1}" if isinstance(page, int) else ""
            )

        return _set_metadata(documents, filename, SourceType.PDF)

    except Exception as exc:
        logger.exception("Failed to load PDF: %s", filename)
        raise IngestionFailed("Could not read PDF file") from exc



def load_docx(filename: str, data: bytes) -> list[Document]:

    try:
        documents = _load_with_tempfile(
            filename,
            data,
            ".docx",
            Docx2txtLoader,
        )

        return _set_metadata(documents, filename, SourceType.DOCX)

    except Exception as exc:
        logger.exception("Failed to load DOCX: %s", filename)
        raise IngestionFailed("Could not read DOCX file") from exc


def load_txt(filename: str, data: bytes) -> list[Document]:

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".txt"
        ) as file:
            file.write(data)
            file.flush()

            documents = TextLoader(
                file.name,
                encoding="utf-8-sig",
            ).load()

        return _set_metadata(documents, filename, SourceType.TXT)

    except Exception as exc:
        logger.exception("Failed to load TXT: %s", filename)
        raise IngestionFailed("Could not read TXT file") from exc


def load_pptx(filename: str, data: bytes) -> list[Document]:

    try:
        documents = _load_with_tempfile(
            filename,
            data,
            ".pptx",
            UnstructuredPowerPointLoader,
            mode="elements",
        )

        for document in documents:
            page = document.metadata.get("page_number")

            document.metadata[LOCATION] = (
                f"slide {page}" if page is not None else ""
            )

        return _set_metadata(documents, filename, SourceType.PPTX)

    except Exception as exc:
        logger.exception("Failed to load PPTX: %s", filename)
        raise IngestionFailed("Could not read PPTX file") from exc


def load_code(filename: str, data: bytes) -> list[Document]:

    try:
        suffix = Path(filename).suffix.lower()

        with tempfile.NamedTemporaryFile(
            suffix=suffix
        ) as file:
            file.write(data)
            file.flush()

            documents = TextLoader(
                file.name,
                encoding="utf-8",
            ).load()

        language = suffix.lstrip(".")

        for document in documents:
            document.metadata["language"] = language

        return _set_metadata(documents, filename, SourceType.CODE)

    except Exception as exc:
        logger.exception("Failed to load code file: %s", filename)
        raise IngestionFailed("Could not read code file") from exc



# main
def load_file(
    filename: str,
    data: bytes,
    source_type: SourceType,
) -> list[Document]:

    loaders = {
        SourceType.PDF: load_pdf,
        SourceType.DOCX: load_docx,
        SourceType.TXT: load_txt,
        SourceType.PPTX: load_pptx,
        SourceType.CODE: load_code,
    }

    loader = loaders.get(source_type)

    if loader is None:
        raise IngestionFailed(
            f"No loader available for source type: {source_type.value}"
        )

    documents = loader(filename, data)

    documents = [
        document
        for document in documents
        if document.page_content.strip()
    ]

    if not documents:
        raise IngestionFailed(
            f"No readable text found in file: {filename}"
        )

    logger.info(
        "Loaded %d document(s) from %s",
        len(documents),
        filename,
    )

    return documents
