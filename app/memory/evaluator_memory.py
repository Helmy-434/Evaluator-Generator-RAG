from __future__ import annotations

import logging
from typing import Any

from app.cache.redis_client import redis_client
from app.core.contract import NS_EVAL_MEMORY

logger = logging.getLogger(__name__)

SESSION_TTL = 1800
MAX_HISTORY_ENTRIES = 32
MAX_FEEDBACK_LENGTH = 2000
MAX_CLAIM_LENGTH = 500


def _session_key(session_id: str) -> str:
    return f"{NS_EVAL_MEMORY}:session:{session_id}"


def record_evaluation(
    session_id: str,
    iteration: int,
    result: Any,
    request_id: str | None = None,
) -> None:

    key = _session_key(session_id)
    entry = {
        "iteration": iteration,
        "request_id": request_id,
        "groundedness_score": getattr(result, "groundedness_score", None),
        "relevance_score": getattr(result, "relevance_score", None),
        "unsupported_claims": [
            str(claim)[:MAX_CLAIM_LENGTH]
            for claim in (getattr(result, "unsupported_claims", []) or [])
        ],
        "is_valid": getattr(result, "is_valid", None),
        "feedback": str(getattr(result, "feedback", "") or "")[:MAX_FEEDBACK_LENGTH],
    }
    try:
        existing = redis_client.get_json(key) or []
        if not isinstance(existing, list):
            existing = []
        existing.append(entry)
        existing = existing[-MAX_HISTORY_ENTRIES:]
        redis_client.set_json(key, existing, ttl=SESSION_TTL)
    except Exception:
        logger.warning("Failed to record evaluation for session %s", session_id, exc_info=True)


def get_session_history(session_id: str) -> list[dict[str, Any]]:
    try:
        history = redis_client.get_json(_session_key(session_id))
    except Exception:
        logger.warning("Failed to read evaluator history for session %s",
                       session_id, exc_info=True)
        return []
    return history if isinstance(history, list) else []
