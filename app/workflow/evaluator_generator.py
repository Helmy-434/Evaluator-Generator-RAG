from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.documents import Document

from app.agents.citations import renumber_citations
from app.agents.evaluator import Evaluator, EvaluationError, EvaluationOutputError
from app.agents.generator import Generator, GenerationError
from app.agents.prompts import REFUSAL_SENTENCE

log = logging.getLogger(__name__)
MAX_ITERATIONS = 4
FALLBACK_FEEDBACK = "Remove unsupported statements and keep [Passage N] citations accurate."
EventHook = Callable[[str, int, Any], None]


@dataclass
class LoopResult:
    answer: str
    validated: bool
    iterations_used: int
    insufficient_knowledge: bool
    sources: list
    evaluator_feedback: str | None
    note: str | None = None


def _emit(hook: EventHook | None, kind: str, iteration: int, payload: Any) -> None:
    if hook:
        try:
            hook(kind, iteration, payload)
        except Exception:
            log.warning("Workflow event hook failed", exc_info=True)


def run_loop(
    question: str,
    documents: list[Document],
    generator: Generator,
    evaluator: Evaluator,
    max_iterations: int = MAX_ITERATIONS,
    on_event: EventHook | None = None,
) -> LoopResult:
    if not documents:
        return LoopResult(REFUSAL_SENTENCE, True, 0, True, [], None,
                          "No relevant sources found.")

    previous: dict[str, Any] | None = None
    feedback: str | None = None
    previous_text: str | None = None

    for iteration in range(1, max_iterations + 1):
        try:
            draft = generator.generate(
                question=question,
                documents=documents,
                evaluator_feedback=feedback,
                previous_draft=previous_text,
            )
        except GenerationError:
            if previous is None:
                raise
            text, sources = _finalize(previous, documents, generator)
            return LoopResult(text, False, iteration - 1,
                              previous["insufficient_knowledge"], sources, feedback,
                              "Generator failed; returning previous draft.")
        previous = draft
        _emit(on_event, "generation", iteration, draft)

        try:
            evaluation = evaluator.evaluate(
                question=question,
                documents=documents,
                draft_answer=draft["draft_answer"],
                insufficient_knowledge=draft["insufficient_knowledge"],
            )
        except EvaluationOutputError:
            evaluation = evaluator.evaluate(
                question=question,
                documents=documents,
                draft_answer=draft["draft_answer"],
                insufficient_knowledge=draft["insufficient_knowledge"],
            )
        except EvaluationError:
            text, sources = _finalize(draft, documents, generator)
            return LoopResult(text, False, iteration,
                              draft["insufficient_knowledge"], sources, None,
                              "Evaluator unavailable; answer not validated.")
        _emit(on_event, "evaluation", iteration, evaluation)

        if evaluation.is_valid:
            text, sources = _finalize(draft, documents, generator)
            return LoopResult(text, True, iteration,
                              draft["insufficient_knowledge"], sources, None)
        feedback = evaluation.feedback or FALLBACK_FEEDBACK
        previous_text = draft["draft_answer"]

    text, sources = _finalize(previous, documents, generator)
    return LoopResult(text, False, max_iterations,
                      previous["insufficient_knowledge"], sources, feedback,
                      "Maximum iterations reached; answer not fully validated.")


def _finalize(draft: dict[str, Any], documents: list[Document], generator: Generator):
    if draft["insufficient_knowledge"]:
        return draft["draft_answer"], []
    text, order = renumber_citations(draft["draft_answer"], len(documents))
    return text, generator.build_sources(order, documents)
