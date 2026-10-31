from __future__ import annotations

import logging
from typing import Any

from app.cache.redis_client import redis_client
from app.contract import NS_EVAL_MEMORY

log = logging.getLogger(__name__)
SESSION_TTL = 1800
MAX_HISTORY_ENTRIES = 32


def _session_key(session_id: str) -> str:
    return f"{NS_EVAL_MEMORY}:session:{session_id}"


def record_evaluation(
    session_id: str, iteration: int, result: Any, request_id: str | None = None
) -> None:
    entry = {
        "iteration": iteration,
        "request_id": request_id,
        "groundedness_score": getattr(result, "groundedness_score", None),
        "relevance_score": getattr(result, "relevance_score", None),
        "unsupported_claims": getattr(result, "unsupported_claims", []),
        "is_valid": getattr(result, "is_valid", None),
        "feedback": getattr(result, "feedback", None),
    }
    try:
        history = redis_client.get_json(_session_key(session_id))
        history = history if isinstance(history, list) else []
        history.append(entry)
        redis_client.set_json(
            _session_key(session_id), history[-MAX_HISTORY_ENTRIES:], ttl=SESSION_TTL
        )
    except Exception:
        log.warning("Evaluator memory write failed", exc_info=True)


def get_session_history(session_id: str) -> list[dict[str, Any]]:
    try:
        history = redis_client.get_json(_session_key(session_id))
        return history if isinstance(history, list) else []
    except Exception:
        log.warning("Evaluator memory read failed", exc_info=True)
        return []
