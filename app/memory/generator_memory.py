"""Generator memory: caches answer results and records per-iteration drafts."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.cache.redis_client import redis_client
from app.contract import NS_GEN_MEMORY, NS_ANSWER, get_corpus_version

logger = logging.getLogger(__name__)

# Default TTL for cached answers (1 hour).  Session histories live shorter.
ANSWER_TTL = 3600
SESSION_TTL = 1800  # 30 min


def _answer_key(question: str, corpus_version: str) -> str:
    """Deterministic cache key: same question + same corpus = cache hit."""
    q_hash = hashlib.sha256(question.strip().lower().encode()).hexdigest()[:16]
    return f"{NS_ANSWER}:{corpus_version}:{q_hash}"


def _session_key(session_id: str) -> str:
    return f"{NS_GEN_MEMORY}:session:{session_id}"


# ── Answer cache ─────────────────────────────────────────────────────────────

def get_cached_answer(question: str) -> dict[str, Any] | None:
    """Return a cached ChatResponse dict if one exists for the current corpus."""
    version = get_corpus_version(redis_client)
    key = _answer_key(question, version)
    data = redis_client.get_json(key)
    if data is not None:
        logger.info("Answer cache hit for key %s", key)
    return data


def cache_answer(question: str, response: dict[str, Any]) -> bool:
    """Store a ChatResponse dict keyed to the current corpus version."""
    version = get_corpus_version(redis_client)
    key = _answer_key(question, version)
    ok = redis_client.set_json(key, response, ttl=ANSWER_TTL)
    if ok:
        logger.info("Answer cached under key %s", key)
    return ok


# ── Per-session iteration history ────────────────────────────────────────────

def record_draft(session_id: str, iteration: int, draft: dict[str, Any]) -> None:
    """Append a generation record to the session's history list.

    Called by the workflow's ``on_event`` hook with kind="generation".
    Each entry stores the draft text, refusal flag, and cited indices
    so the full refinement trajectory is recoverable for debugging.
    """
    key = _session_key(session_id)
    entry = {
        "iteration": iteration,
        "draft_answer": draft.get("draft_answer", ""),
        "insufficient_knowledge": draft.get("insufficient_knowledge", False),
        "cited_indices": draft.get("cited_indices", []),
    }
    try:
        # Append to an existing list, or start a new one.
        existing = redis_client.get_json(key) or []
        existing.append(entry)
        redis_client.set_json(key, existing, ttl=SESSION_TTL)
    except Exception:
        logger.warning("Failed to record generator draft for session %s", session_id, exc_info=True)


def get_session_history(session_id: str) -> list[dict[str, Any]]:
    """Return the full list of draft records for a session (may be empty)."""
    return redis_client.get_json(_session_key(session_id)) or []

