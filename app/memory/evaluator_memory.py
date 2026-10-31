"""Evaluator memory: records per-iteration evaluation verdicts."""
from __future__ import annotations

import logging
from typing import Any

from app.cache.redis_client import redis_client
from app.contract import NS_EVAL_MEMORY

logger = logging.getLogger(__name__)

SESSION_TTL = 1800  # 30 min — same lifetime as generator session history


def _session_key(session_id: str) -> str:
    return f"{NS_EVAL_MEMORY}:session:{session_id}"


def record_evaluation(session_id: str, iteration: int, result: Any) -> None:
    """Append an evaluation record to the session's history list.

    Called by the workflow's ``on_event`` hook with kind="evaluation".
    ``result`` is an ``EvaluationResult`` dataclass — we serialise the
    fields we care about so the history is JSON-safe.
    """
    key = _session_key(session_id)
    entry = {
        "iteration": iteration,
        "groundedness_score": getattr(result, "groundedness_score", None),
        "relevance_score": getattr(result, "relevance_score", None),
        "unsupported_claims": getattr(result, "unsupported_claims", []),
        "is_valid": getattr(result, "is_valid", None),
        "feedback": getattr(result, "feedback", None),
    }
    try:
        existing = redis_client.get_json(key) or []
        existing.append(entry)
        redis_client.set_json(key, existing, ttl=SESSION_TTL)
    except Exception:
        logger.warning("Failed to record evaluation for session %s", session_id, exc_info=True)


def get_session_history(session_id: str) -> list[dict[str, Any]]:
    """Return the full list of evaluation records for a session (may be empty)."""
    return redis_client.get_json(_session_key(session_id)) or []

