from __future__ import annotations

import logging
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

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
from app.agents.prompts import GENERATOR_SYSTEM_PROMPT
from app.knowledge.retriever import Retriever

logger = logging.getLogger(__name__)


class Generator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=GENERATOR_MODEL,
            api_key=GENERATOR_API_KEY,
            base_url=GENERATOR_BASE_URL,
            request_timeout=GENERATOR_TIMEOUT,
            temperature=0.2,
        )

    def add_metadata(self, documents: list[Document]) -> list[SourceRef]:
        """Extracts SourceRef objects from document metadata."""
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

    def create_full_prompt(
        self,
        user_input: str,
        documents: list[Document],
        evaluator_feedback: str | None = None,
    ) -> list[dict[str, str]]:

        context_blocks = []
        for doc in documents:
            meta = doc.metadata or {}
            source_name = meta.get(SOURCE, "unknown")
            location = meta.get(LOCATION)
            header = f"[Source: {source_name}" + (f", Location: {location}]" if location else "]")
            context_blocks.append(f"{header}\n{doc.page_content.strip()}")

        context = "\n\n".join(context_blocks)

        messages = [
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        ]

        user_content = (
            f"Context:\n"
            f'"""\n{context}\n"""\n\n'
            f"Question:\n{user_input}"
        )

        if evaluator_feedback:
            user_content += (
                f"\n\nPrevious Evaluator Feedback:\n"
                f'"""\n{evaluator_feedback}\n"""\n\n'
                f"Please refine your answer to address the evaluator's feedback while adhering strictly to the context."
            )

        messages.append({"role": "user", "content": user_content})
        return messages

    def generate(
        self, prompt: str, evaluator_feedback: str | None = None
    ) -> dict[str, Any]:
        
        retriever = Retriever()
        context = retriever.retrieve(prompt)

        if not context["has_relevant"]:
            logger.info("No relevant context found for the prompt.")
            return {
                "draft_answer": "I do not have sufficient information in the provided sources to answer this question.",
                "insufficient_knowledge": True,
                "sources": [],
            }

        documents: list[Document] = context["documents"]
        full_prompt = self.create_full_prompt(
            user_input=prompt,
            documents=documents,
            evaluator_feedback=evaluator_feedback,
        )
        response = self.llm.invoke(full_prompt)

        return {
            "draft_answer": response.content,
            "insufficient_knowledge": False,
            "sources": self._extract_sources(documents),
        }