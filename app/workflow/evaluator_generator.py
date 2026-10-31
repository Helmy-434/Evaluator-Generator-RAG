from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app.agents.citations import renumber_citations
from app.agents.evaluator import Evaluator, EvaluationError, EvaluationOutputError
from app.agents.generator import Generator, GenerationError
from app.agents.prompts import REFUSAL_SENTENCE

logger = logging.getLogger(__name__)

# Counts the FIRST generation as iteration 1 (confirm with the instructor).
MAX_ITERATIONS = 4
FALLBACK_FEEDBACK = ("Remove every statement not directly supported by the context "
                     "and keep [Passage N] citations accurate.")

# Hook so the memories can record what they own without crossing:
#   on_event("generation", iteration, draft_dict)  -> Generator memory
#   on_event("evaluation", iteration, EvaluationResult) -> Evaluator memory
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


def _emit(hook: EventHook | None, kind: str, i: int, payload: Any) -> None:
    if hook:
        try:
            hook(kind, i, payload)
        except Exception:  # memory/logging must never break the loop
            logger.warning("Event hook failed (%s)", kind, exc_info=True)


def _generate(generator: Generator, **kw) -> dict:
    try:
        return generator.generate(**kw)
    except GenerationError:
        logger.warning("Generation failed, retrying once")
        return generator.generate(**kw)  # second failure propagates


def _evaluate(evaluator: Evaluator, **kw):
    try:
        return evaluator.evaluate(**kw)
    except EvaluationOutputError:  # malformed output: retry once
        logger.warning("Evaluator output unusable, retrying once")
        return evaluator.evaluate(**kw)
    # plain EvaluationError (outage) propagates to the caller below


def _finalize(draft: dict, documents: list[Document], generator: Generator) -> tuple[str, list]:
    if draft["insufficient_knowledge"]:
        return draft["draft_answer"], []
    text, order = renumber_citations(draft["draft_answer"], len(documents))
    return text, generator.build_sources(order, documents)


def run_loop(
    question: str,
    documents: list[Document],
    generator: Generator,
    evaluator: Evaluator,
    max_iterations: int = MAX_ITERATIONS,
    on_event: EventHook | None = None,
) -> LoopResult:
    # Retrieval found nothing relevant: refuse without any LLM call.
    if not documents:
        return LoopResult(REFUSAL_SENTENCE, True, 0, True, [], None,
                          note="No relevant sources found.")

    draft: dict | None = None
    last_ok: dict | None = None
    feedback: str | None = None
    prev_text: str | None = None

    for i in range(1, max_iterations + 1):
        t0 = time.perf_counter()
        try:
            draft = _generate(generator, question=question, documents=documents,
                              evaluator_feedback=feedback, previous_draft=prev_text)
        except GenerationError:
            if last_ok is None:
                raise  # nothing to return: let /api/chat map this to an error response
            text, sources = _finalize(last_ok, documents, generator)
            return LoopResult(text, False, i - 1, last_ok["insufficient_knowledge"],
                              sources, feedback, note="Generator failed; returning previous draft.")
        last_ok = draft
        _emit(on_event, "generation", i, draft)

        try:
            result = _evaluate(evaluator, question=question, documents=documents,
                               draft_answer=draft["draft_answer"],
                               insufficient_knowledge=draft["insufficient_knowledge"])
        except EvaluationError as exc:
            logger.error("Evaluator unavailable at iteration %d: %s", i, exc)
            text, sources = _finalize(draft, documents, generator)
            return LoopResult(text, False, i, draft["insufficient_knowledge"], sources,
                              None, note="Evaluator unavailable; answer not validated.")
        _emit(on_event, "evaluation", i, result)

        logger.info("iteration=%d g=%.2f r=%.2f valid=%s unsupported=%d latency_ms=%d",
                    i, result.groundedness_score, result.relevance_score, result.is_valid,
                    len(result.unsupported_claims), (time.perf_counter() - t0) * 1000)

        if result.is_valid:
            text, sources = _finalize(draft, documents, generator)
            return LoopResult(text, True, i, draft["insufficient_knowledge"], sources, None)

        feedback = result.feedback or FALLBACK_FEEDBACK  # Generator requires non-empty feedback
        prev_text = draft["draft_answer"]

    text, sources = _finalize(draft, documents, generator)
    return LoopResult(text, False, max_iterations, draft["insufficient_knowledge"], sources,
                      feedback, note="Maximum iterations reached; answer not fully validated.")


def build_chain(generator: Generator, evaluator: Evaluator, on_event: EventHook | None = None):
    """LCEL entry point: input {'question', 'documents'} -> LoopResult."""
    return RunnableLambda(lambda x: run_loop(
        x["question"], x["documents"], generator, evaluator, on_event=on_event))
