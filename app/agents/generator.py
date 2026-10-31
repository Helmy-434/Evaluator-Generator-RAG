from __future__ import annotations

import logging
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from app.agents.prompts import GENERATOR_SYSTEM_PROMPT
from app.contract import (
    GENERATOR_API_KEY,
    GENERATOR_BASE_URL,
    GENERATOR_MODEL,
    GENERATOR_TIMEOUT,
    SOURCE,
    TYPE,
    LOCATION,
    SourceRef,
)

logger = logging.getLogger(__name__)


class Generator:

    def __init__(self, llm: ChatOpenAI | None = None):
        self.llm = llm or ChatOpenAI(
            model=GENERATOR_MODEL,
            api_key=GENERATOR_API_KEY,
            base_url=GENERATOR_BASE_URL,
            request_timeout=GENERATOR_TIMEOUT,
            temperature=0.2,
        )
        self.output_parser = StrOutputParser()

    def extract_sources(self, documents: list[Document]) -> list[SourceRef]:
        sources: list[SourceRef] = []
        for doc in documents:
            meta = doc.metadata or {}
            sources.append(
                SourceRef(
                    source=meta.get(SOURCE, "unknown"),
                    type=meta.get(TYPE, "unknown"),
                    location=meta.get(LOCATION),
                    snippet=doc.page_content[:200],
                )
            )
        return sources

    def _build_context_str(self, documents: list[Document]) -> str:
        """Formats documents with source metadata headers into an XML-safe context block."""
        blocks = []
        for doc in documents:
            meta = doc.metadata or {}
            src = meta.get(SOURCE, "unknown")
            loc = meta.get(LOCATION)
            header = f"[Source: {src}" + (f", Location: {loc}]" if loc else "]")
            blocks.append(f"{header}\n{doc.page_content.strip()}")
        return "\n\n".join(blocks)

    def build_prompt_messages(
        self,
        question: str,
        documents: list[Document],
        evaluator_feedback: str | None = None,
        previous_draft: str | None = None,
    ) -> list[tuple[str, str]]:

        context_str = self._build_context_str(documents)

        user_content = (
            f"<context>\n{context_str}\n</context>\n\n"
            f"Question: {question}"
        )

        if evaluator_feedback and previous_draft:
            user_content += (
                f"\n\n<previous_draft>\n{previous_draft}\n</previous_draft>\n\n"
                f"<evaluator_feedback>\n{evaluator_feedback}\n</evaluator_feedback>\n\n"
                f"Instruction: Refine the previous draft to address the evaluator's feedback while adhering strictly to the <context>."
            )

        return [
            ("system", GENERATOR_SYSTEM_PROMPT),
            ("user", user_content),
        ]

    def generate(
        self,
        question: str,
        documents: list[Document],
        evaluator_feedback: str | None = None,
        previous_draft: str | None = None,
    ) -> dict[str, Any]:
       
        
        if not documents:
            logger.info("No documents provided for question: %s", question)
            return {
                "draft_answer": "I do not have sufficient information in the provided sources to answer this question.",
                "insufficient_knowledge": True,
                "sources": [],
            }

        prompt_messages = self.build_prompt_messages(
            question=question,
            documents=documents,
            evaluator_feedback=evaluator_feedback,
            previous_draft=previous_draft,
        )

        prompt_template = ChatPromptTemplate.from_messages(prompt_messages)
        chain = prompt_template | self.llm | self.output_parser

        try:
            draft_answer = chain.invoke({})
        except Exception as exc:
            logger.error("LLM generation failed for question '%s': %s", question, exc, exc_info=True)
            return {
                "draft_answer": "An error occurred while generating the answer. Please try again later.",
                "insufficient_knowledge": False,
                "sources": self.extract_sources(documents),
                "error": str(exc),
            }

        is_insufficient = "do not have sufficient information" in draft_answer.lower()

        return {
            "draft_answer": draft_answer,
            "insufficient_knowledge": is_insufficient,
            "sources": self.extract_sources(documents),
        }