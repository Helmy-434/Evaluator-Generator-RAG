from __future__ import annotations

import logging
from typing import Any

from app.cache.redis_client import redis_client
from app.contract import NS_GEN_MEMORY

log = logging.getLogger(__name__)
SESSION_TTL = 1800
MAX_HISTORY_ENTRIES = 32
MAX_DRAFT_LENGTH = 4000


def _session_key(session_id: str) -> str:
    return f"{NS_GEN_MEMORY}:session:{session_id}"


def record_draft(
    session_id: str, iteration: int, draft: dict[str, Any], request_id: str | None = None
) -> None:
    entry = {
        "iteration": iteration,
        "request_id": request_id,
        "draft_answer": str(draft.get("draft_answer", ""))[:MAX_DRAFT_LENGTH],
        "insufficient_knowledge": draft.get("insufficient_knowledge", False),
        "cited_indices": draft.get("cited_indices", []),
    }
    try:
        history = redis_client.get_json(_session_key(session_id))
        history = history if isinstance(history, list) else []
        history.append(entry)
        redis_client.set_json(
            _session_key(session_id), history[-MAX_HISTORY_ENTRIES:], ttl=SESSION_TTL
        )
    except Exception:
        log.warning("Generator memory write failed", exc_info=True)


def get_session_history(session_id: str) -> list[dict[str, Any]]:
    try:
        history = redis_client.get_json(_session_key(session_id))
        return history if isinstance(history, list) else []
    except Exception:
        log.warning("Generator memory read failed", exc_info=True)
        return []
