from __future__ import annotations

from typing import Any

from app.memory import evaluator_memory, generator_memory


def build_memory_hook(session_id: str, request_id: str | None = None):
    def record(kind: str, iteration: int, payload: Any) -> None:
        if kind == "generation":
            generator_memory.record_draft(session_id, iteration, payload, request_id)
        elif kind == "evaluation":
            evaluator_memory.record_evaluation(session_id, iteration, payload, request_id)

    return record
