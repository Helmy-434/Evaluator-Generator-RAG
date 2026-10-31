from __future__ import annotations

import logging
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agents.citations import is_refusal_answer, cited_indices
from app.agents.context_formatter import format_context, escape_xml_delimiters
from app.contract import (
    GENERATOR_API_KEY,
    GENERATOR_BASE_URL,
    GENERATOR_MODEL,
    GENERATOR_TIMEOUT,
    SOURCE,
    TYPE,
    SourceType,
    SourceRef,
    location_or_none,
)
from app.agents.prompts import GENERATOR_SYSTEM_PROMPT, REFUSAL_SENTENCE

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Raised when the Generator LLM call fails or times out."""
    pass


class Generator:

    def __init__(self, llm: ChatOpenAI | None = None):
        if not GENERATOR_API_KEY and not llm:
            raise ValueError(
                "GENERATOR_API_KEY is not set. Please ensure GENERATOR_API_KEY is in your environment or .env file."
            )

        self.llm = llm or ChatOpenAI(
            model=GENERATOR_MODEL,
            api_key=GENERATOR_API_KEY,
            base_url=GENERATOR_BASE_URL,
            request_timeout=GENERATOR_TIMEOUT,
            temperature=0.2,
        )
        self.output_parser = StrOutputParser()

        self.initial_prompt = ChatPromptTemplate.from_messages([
            ("system", GENERATOR_SYSTEM_PROMPT),
            (
                "user",
                "<context>\n{context}\n</context>\n\n"
                "Question: {question}",
            ),
        ])

        self.refine_prompt = ChatPromptTemplate.from_messages([
            ("system", GENERATOR_SYSTEM_PROMPT),
            (
                "user",
                "<context>\n{context}\n</context>\n\n"
                "Question: {question}\n\n"
                "<previous_draft>\n{previous_draft}\n</previous_draft>\n\n"
                "<evaluator_feedback>\n{evaluator_feedback}\n</evaluator_feedback>\n\n"
                "Instruction: Refine the previous draft to address the evaluator's feedback while adhering strictly to the <context>.",
            ),
        ])

        self.initial_chain = self.initial_prompt | self.llm | self.output_parser
        self.refine_chain = self.refine_prompt | self.llm | self.output_parser

    def build_sources(self, indices: list[int], documents: list[Document]) -> list[SourceRef]:
        sources: list[SourceRef] = []
        for i in indices:
            doc = documents[i - 1]
            meta = doc.metadata or {}
            try:
                src_type = SourceType(meta.get(TYPE)) if meta.get(TYPE) else SourceType.TXT
            except ValueError:
                src_type = SourceType.TXT
            sources.append(
                SourceRef(
                    source=meta.get(SOURCE, "unknown"),
                    type=src_type,
                    location=location_or_none(meta),
                    snippet=doc.page_content[:200],
                )
            )
        return sources

    _build_sources = build_sources

    def generate(
        self,
        question: str,
        documents: list[Document],
        evaluator_feedback: str | None = None,
        previous_draft: str | None = None,
    ) -> dict[str, Any]:

        if (evaluator_feedback and not previous_draft) or (previous_draft and not evaluator_feedback):
            raise ValueError(
                "Both evaluator_feedback and previous_draft must be provided together during refinement."
            )

        if not documents:
            logger.info("No documents provided for generation.")
            return {
                "draft_answer": REFUSAL_SENTENCE,
                "insufficient_knowledge": True,
                "sources": [],
            }

        context_str = format_context(documents)

        try:
            if evaluator_feedback and previous_draft:
                draft_answer = self.refine_chain.invoke({
                    "context": context_str,
                    "question": question,
                    "previous_draft": escape_xml_delimiters(previous_draft),
                    "evaluator_feedback": escape_xml_delimiters(evaluator_feedback),
                })
            else:
                draft_answer = self.initial_chain.invoke({
                    "context": context_str,
                    "question": question,
                })
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc, exc_info=True)
            raise GenerationError(f"Generator LLM call failed: {exc}") from exc

        is_insufficient = is_refusal_answer(draft_answer)
        indices = [] if is_insufficient else cited_indices(draft_answer, len(documents))
        if not is_insufficient and not indices:
            logger.warning("Non-refusal draft has no valid [Passage N] citations.")

        return {
            "draft_answer": draft_answer,
            "insufficient_knowledge": is_insufficient,
            "sources": self.build_sources(indices, documents),
            "cited_indices": indices,  # raw numbering, used later by renumber_citations
        }
