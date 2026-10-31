from __future__ import annotations

import logging
from typing import Any

from app.cache.answer_cache import cache_answer, get_cached_answer
from app.cache.redis_client import redis_client
from app.contract import NS_GEN_MEMORY

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 min
MAX_HISTORY_ENTRIES = 32
MAX_DRAFT_LENGTH = 4000


def _session_key(session_id: str) -> str:
    return f"{NS_GEN_MEMORY}:session:{session_id}"


def record_draft(
    session_id: str,
    iteration: int,
    draft: dict[str, Any],
    request_id: str | None = None,
) -> None:

    key = _session_key(session_id)
    entry = {
        "iteration": iteration,
        "request_id": request_id,
        "draft_answer": str(draft.get("draft_answer", ""))[:MAX_DRAFT_LENGTH],
        "insufficient_knowledge": draft.get("insufficient_knowledge", False),
        "cited_indices": draft.get("cited_indices", []),
    }
    try:
        # Append to an existing list, or start a new one.
        existing = redis_client.get_json(key) or []
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        existing = existing[-MAX_HISTORY_ENTRIES:]
        redis_client.set_json(key, existing, ttl=SESSION_TTL)
    except Exception:
        logger.warning("Failed to record generator draft for session %s", session_id, exc_info=True)


def get_session_history(session_id: str) -> list[dict[str, Any]]:
    try:
        history = redis_client.get_json(_session_key(session_id))
    except Exception:
        logger.warning("Failed to read generator history for session %s",
                       session_id, exc_info=True)
        return []
    return history if isinstance(history, list) else []
