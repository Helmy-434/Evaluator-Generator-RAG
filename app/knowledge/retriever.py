from app.contract import get_vector_store

import logging
log = logging.getLogger(__name__)


class Retriever:
    def __init__(self,top_k: int = 5, score_threshold: float = 0.4):
        self.vector_store = get_vector_store()
        self.top_k = top_k
        self.score_threshold = score_threshold
        log.info("Initialized retriever.")
        
    def retrieve(self, query: str):
        log.info(f"Searching top_{self.top_k} chunks for query: '{query[:50]}...'")
        
        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(
                query=query,
                k=self.top_k
            )
        except Exception as exc:
            log.error(f"Vector store query failed: {exc}")
            raise
        
        relevant_docs = [
            doc for doc, score in results_with_scores 
            if score >= self.score_threshold
        ]
        
        if not relevant_docs:
            log.info("No context chunks met score threshold.")
            
        return {
            "documents": relevant_docs,
            "has_relevant": len(relevant_docs) > 0,
            "count": len(relevant_docs)
        }

