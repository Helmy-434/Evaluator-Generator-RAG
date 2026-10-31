from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

from langchain_core.documents import Document

from app.cache.redis_client import redis_client
from app.contract import (
    CHUNK_ID,
    LOCATION,
    SOURCE,
    SOURCE_ID,
    TYPE,
    SourceInfo,
    SourceType,
    bump_corpus_version,
    get_vector_store,
)

log = logging.getLogger(__name__)

ADD_BATCH_SIZE = 100
DELETE_BATCH_SIZE = 500
_METADATA_KEYS = (SOURCE_ID, SOURCE, TYPE, CHUNK_ID, LOCATION)


# Helpers methods starts with _

def _clean_metadata(meta: dict[str, Any]) -> dict[str, str]:
    
    cleaned = {}
    
    for key in _METADATA_KEYS:
        value = meta.get(key)
        value = getattr(value, "value", value)  # SourceType.PDF -> "pdf"
        cleaned[key] = "" if value is None else str(value)
        
    if not cleaned[SOURCE_ID] or not cleaned[CHUNK_ID]:
        raise ValueError("chunk metadata must contain non-empty source_id and chunk_id")
    
    return cleaned


def _ids_for_source(source_id: str) -> list[str]:
    store = get_vector_store()
    result = store.get(where={SOURCE_ID: source_id}, include=["metadatas"])
    return list(result.get("ids") or [])


def _delete_ids(ids: list[str]) -> None:
    store = get_vector_store()
    for i in range(0, len(ids), DELETE_BATCH_SIZE):
        store.delete(ids=ids[i : i + DELETE_BATCH_SIZE])



# Write Ops
def add_chunks(chunks: list[Document]) -> tuple[int, str | None]:

    if not chunks:
        return 0, None

    for doc in chunks:
        doc.metadata = _clean_metadata(doc.metadata)
    ids = [doc.metadata[CHUNK_ID] for doc in chunks]

    store = get_vector_store()
    
    try:
        for i in range(0, len(chunks), ADD_BATCH_SIZE):
            batch = chunks[i : i + ADD_BATCH_SIZE]
            store.add_documents(batch, ids=ids[i : i + ADD_BATCH_SIZE])
    
    except Exception:
        log.exception("add_chunks failed, rolling back %d chunks", len(ids))
        try:
            _delete_ids(ids)
        except Exception:
            log.exception("rollback failed")
        raise

    version = bump_corpus_version(redis_client)
    
    log.info("added %d chunks (source_id=%s, corpus_version=%s)",
             len(chunks), chunks[0].metadata[SOURCE_ID], version)
    
    return len(chunks), version



def delete_source(source_id: str) -> tuple[int, str | None]:
    
    ids = _ids_for_source(source_id)
    
    if ids:
        _delete_ids(ids)
        
    version = bump_corpus_version(redis_client)
    
    log.info("deleted %d chunks (source_id=%s, corpus_version=%s)", len(ids), source_id, version)
    
    return len(ids), version


def replace_source(source_id: str, chunks: list[Document]) -> tuple[int, str | None]:
    
    old_ids = _ids_for_source(source_id)
    
    if old_ids:
        _delete_ids(old_ids)
        
    if not chunks:
        return 0, bump_corpus_version(redis_client)
    
    return add_chunks(chunks)