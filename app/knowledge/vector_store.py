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
