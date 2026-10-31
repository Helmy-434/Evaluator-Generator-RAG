from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from app.cache.redis_client import redis_client
from app.contract import EVALUATOR_MODEL, GENERATOR_MODEL, NS_ANSWER

log = logging.getLogger(__name__)
ANSWER_TTL = 3600
PROMPT_VERSION = "v1"


def _answer_key(
    question: str,
    corpus_version: str,
    *,
    generator_model: str = GENERATOR_MODEL,
    evaluator_model: str = EVALUATOR_MODEL,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    normalized = re.sub(r"\s+", " ", question.strip().lower())
    value = "\x1f".join(
        (normalized, corpus_version, generator_model, evaluator_model, prompt_version)
    )
    return f"{NS_ANSWER}:{corpus_version}:{hashlib.sha256(value.encode()).hexdigest()[:16]}"


def get_cached_answer(question: str, corpus_version: str) -> dict[str, Any] | None:
    try:
        return redis_client.get_json(_answer_key(question, corpus_version))
    except Exception:
        log.warning("Answer cache read failed", exc_info=True)
        return None


def cache_answer(question: str, response: dict[str, Any], corpus_version: str) -> bool:
    if response.get("validated") is not True:
        return False
    try:
        return redis_client.set_json(
            _answer_key(question, corpus_version), response, ttl=ANSWER_TTL
        )
    except Exception:
        log.warning("Answer cache write failed", exc_info=True)
        return False


def current_corpus_version() -> str:
    from app.contract import get_corpus_version

    try:
        return get_corpus_version(redis_client)
    except Exception:
        log.warning("Corpus version read failed", exc_info=True)
        return "0"
