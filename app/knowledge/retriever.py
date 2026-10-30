from contract import get_vector_store


class Retriever:
    def __init__(self,top_k: int = 5, score_threshold: float = 0.4):
        self.vector_store = get_vector_store()
        self.vector_retriever = self.vector_store.as_retriever(search_type="similarity", search_kwargs={"k": top_k})
        self.top_k = top_k
        self.score_threshold = score_threshold

    def retrieve(self, query: str):
        results_with_scores = self.vector_store.similarity_search_with_relevance_scores(
            query=query,
            k=self.top_k
        )
        
        relevant_docs = [
            doc for doc, score in results_with_scores 
            if score >= self.score_threshold
        ]
        
        return relevant_docs

