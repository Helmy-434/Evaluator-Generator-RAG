import hashlib
import logging

from langchain_core.documents import Document

from app.contract import (
    IngestResult,
    SourceType,
    SOURCE,
    TYPE,
    SOURCE_ID,
    CHUNK_ID,
    bump_corpus_version,
    get_vector_store,
)
from app.cache.ingestion_cache import IngestionCache
from app.cache.redis_client import redis_client
from app.core.errors import InvalidRequest
from app.ingestion.validators import validate_file, validate_url
from app.ingestion.file_loaders import load_file
from app.ingestion.web_loaders import load_web_page, load_wikipedia_page
from app.ingestion.cleaning import clean_documents
from app.ingestion.chunking import split_documents
from app.knowledge.vector_store import source_exists


logger = logging.getLogger(__name__)

ingestion_cache = IngestionCache()


def generate_source_id(content: bytes) -> str:
    """Generate a stable ID from source content."""
    return hashlib.sha256(content).hexdigest()


def documents_to_bytes(documents: list[Document]) -> bytes:
    """Convert extracted document content into bytes for hashing."""
    content = "\n".join(
        document.page_content for document in documents
    )
    return content.encode("utf-8")


def _already_exists(
    source_id: str,
    source: str,
    source_type: SourceType,
) -> IngestResult:
    
    return IngestResult(
        source_id=source_id,
        source=source,
        type=source_type,
        status="already_exists",
        message="This source has already been ingested",
        chunks_added=0,
    )


def _ingest_documents(
    documents: list[Document],
    source_id: str,
    source: str,
    source_type: SourceType,
    cache_content: bytes,
) -> IngestResult:
    """Clean, chunk, store documents, and update caches."""

    if not documents:
        raise InvalidRequest("No readable content found in source")

    documents = clean_documents(documents)

    if not documents:
        raise InvalidRequest("Source contains no usable text after cleaning")

    for document in documents:
        document.metadata[SOURCE] = source
        document.metadata[TYPE] = source_type.value

    chunks = split_documents(
        documents=documents,
        source_id=source_id,
    )

    if not chunks:
        raise InvalidRequest("No chunks were generated from source")

    vector_store = get_vector_store()

    vector_store.add_documents(
        documents=chunks,
        ids=[
            chunk.metadata[CHUNK_ID]
            for chunk in chunks
        ],
    )

    version = bump_corpus_version(redis_client)

    cache_saved = ingestion_cache.set(
        cache_content,
        source_id,
    )

    logger.info(
        "Ingestion completed: source_id=%s, chunks=%d",
        source_id,
        len(chunks),
    )

    return IngestResult(
        source_id=source_id,
        source=source,
        type=source_type,
        status="ingested",
        chunks_added=len(chunks),
        cache_synced=version is not None and cache_saved,
    )



def _check_existing_source(content: bytes,source_id: str,source: str,source_type: SourceType) -> IngestResult | None:
    
    cached_source_id = ingestion_cache.get(content)

    if cached_source_id:
        if source_exists(cached_source_id):
            return _already_exists(
                cached_source_id,
                source,
                source_type,
            )

    if source_exists(source_id):
        ingestion_cache.set(content, source_id)

        return _already_exists(
            source_id,
            source,
            source_type,
        )

    return None



def ingest_file(filename: str, data: bytes) -> IngestResult:

    source_type = validate_file(filename, data)
    source_id = generate_source_id(data)

    existing = _check_existing_source(
        content=data,
        source_id=source_id,
        source=filename,
        source_type=source_type,
    )

    if existing:
        return existing

    documents = load_file(filename, data)

    return _ingest_documents(
        documents=documents,
        source_id=source_id,
        source=filename,
        source_type=source_type,
        cache_content=data,
    )



def ingest_url(url: str) -> IngestResult:

    url = validate_url(url)

    documents = load_web_page(url)

    content = documents_to_bytes(documents)
    source_id = generate_source_id(content)

    existing = _check_existing_source(
        content=content,
        source_id=source_id,
        source=url,
        source_type=SourceType.WEB,
    )

    if existing:
        return existing

    return _ingest_documents(
        documents=documents,
        source_id=source_id,
        source=url,
        source_type=SourceType.WEB,
        cache_content=content,
    )



def ingest_wikipedia(page: str, lang: str = "en") -> IngestResult:

    documents = load_wikipedia_page(page, lang)

    content = documents_to_bytes(documents)
    source_id = generate_source_id(content)

    source = documents[0].metadata.get(SOURCE, page)

    existing = _check_existing_source(
        content=content,
        source_id=source_id,
        source=source,
        source_type=SourceType.WIKIPEDIA,
    )

    if existing:
        return existing

    return _ingest_documents(
        documents=documents,
        source_id=source_id,
        source=source,
        source_type=SourceType.WIKIPEDIA,
        cache_content=content,
    )