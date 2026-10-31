from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from app.cache.redis_client import redis_client
from app.contract import (
    EVALUATOR_MODEL,
    GENERATOR_MODEL,
    NS_ANSWER,
    get_corpus_version,
)

logger = logging.getLogger(__name__)

ANSWER_TTL = 3600
ANSWER_CACHE_PROMPT_VERSION = "v1"


def _normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _answer_key(
    question: str,
    corpus_version: str,
    *,
    generator_model: str = GENERATOR_MODEL,
    evaluator_model: str = EVALUATOR_MODEL,
    prompt_version: str = ANSWER_CACHE_PROMPT_VERSION,
) -> str:
    dimensions = "\x1f".join(
        (_normalize_question(question), corpus_version, generator_model,
         evaluator_model, prompt_version)
    )
    q_hash = hashlib.sha256(dimensions.encode()).hexdigest()[:16]
    return f"{NS_ANSWER}:{corpus_version}:{q_hash}"


def get_cached_answer(question: str, corpus_version: str) -> dict[str, Any] | None:
    key = _answer_key(question, corpus_version)
    try:
        data = redis_client.get_json(key)
    except Exception:
        logger.warning("Failed to read answer cache", exc_info=True)
        return None
    if data is not None:
        logger.info("Answer cache hit for key %s", key)
    return data


def cache_answer(
    question: str,
    response: dict[str, Any],
    corpus_version: str,
) -> bool:
    if response.get("validated") is not True:
        logger.info("Skipping cache for unvalidated answer")
        return False

    key = _answer_key(question, corpus_version)
    try:
        ok = redis_client.set_json(key, response, ttl=ANSWER_TTL)
    except Exception:
        logger.warning("Failed to write answer cache", exc_info=True)
        return False
    if ok:
        logger.info("Answer cached under key %s", key)
    return ok


def current_corpus_version() -> str:
    """Snapshot the version once at request start for cache read and write."""
    try:
        return get_corpus_version(redis_client)
    except Exception:
        logger.warning("Failed to read corpus version", exc_info=True)
        return "0"
