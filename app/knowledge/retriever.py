from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from app.contract import (
    CHUNK_ID,
    LOCATION,
    SOURCE_ID,
    get_vector_store,
)

log = logging.getLogger(__name__)

RELEVANCE_SCORE_KEY = "score"


class EmptyKnowledgeBaseError(Exception):
    pass


class RetrievalError(Exception):
    pass


@dataclass
class ScoredChunk:
    document: Document
    score: float
    source_id: str | None
    location: str | None
    chunk_id: str | None


@dataclass
class RetrievalResult:
    chunks: list[ScoredChunk]
    best_score: float
    has_relevant: bool


class KnowledgeRetriever(BaseRetriever):
    
    vector_store: Any = Field(default_factory=get_vector_store)
    k: int = 5
    score_threshold: float = 0.4

    def retrieve(self, query: str) -> RetrievalResult:
        query_str = query.strip()
        if not query_str:
            raise ValueError("Query cannot be blank.")

        try:
            sample = self.vector_store.get(limit=1)
            if not sample or not sample.get("ids"):
                raise EmptyKnowledgeBaseError("The knowledge base has no documents indexed.")
        except EmptyKnowledgeBaseError:
            raise
        except Exception as exc:
            log.error("Failed to inspect vector store: %s", exc)
            raise RetrievalError(f"Vector store check failed: {exc}") from exc

        log.info("Searching top_%d chunks for query: '%s...'", self.k, query_str[:50])

        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(
                query=query_str,
                k=self.k,
            )
        except Exception as exc:
            log.error("Vector store query failed: %s", exc)
            raise RetrievalError(f"Vector store query failed: {exc}") from exc

        best_score = results_with_scores[0][1] if results_with_scores else 0.0

        scored_chunks = [
            ScoredChunk(
                document=doc,
                score=score,
                source_id=doc.metadata.get(SOURCE_ID),
                location=doc.metadata.get(LOCATION),
                chunk_id=doc.metadata.get(CHUNK_ID),
            )
            for doc, score in results_with_scores
            if score >= self.score_threshold
        ]

        if not scored_chunks:
            log.info("No context chunks met score threshold (best: %.2f)", best_score)

        return RetrievalResult(
            chunks=scored_chunks,
            best_score=best_score,
            has_relevant=len(scored_chunks) > 0,
        )

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> list[Document]:
        """LangChain LCEL hook for retriever.invoke(query)."""
        result = self.retrieve(query)
        docs = []
        for chunk in result.chunks:
            doc = chunk.document
            doc.metadata[RELEVANCE_SCORE_KEY] = chunk.score
            docs.append(doc)
        return docs