from langchain_openai import ChatOpenAI
from app.contract import (
    GENERATOR_API_KEY,
    GENERATOR_BASE_URL,
    GENERATOR_MODEL,
    GENERATOR_TIMEOUT,
)
from app.agents.prompts import GENERATOR_SYSTEM_PROMPT
from app.knowledge import Retriever
import logging

logger = logging.getLogger(__name__)


class Generator:
    def __init__(self):
        self.llm =ChatOpenAI(
        model=GENERATOR_MODEL,      
        api_key=GENERATOR_API_KEY,  
        base_url=GENERATOR_BASE_URL, 
        request_timeout=GENERATOR_TIMEOUT,
        temperature=0.2,
    )

    def create_full_prompt(
        self,
        user_input: str,
        context: str,
        evaluator_feedback: str | None = None,
    ) -> list[dict[str, str]]:
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
    
    def generate(self, prompt: str) -> str:
            retriever = Retriever()
            context = retriever.retrieve(prompt)
            if not context.has_relevant:
                logging.log(logging.INFO, "No relevant context found for the prompt.")
                return {"message": "No relevant context found for the prompt.", "insufficient_knowledge": True}
                    
            full_prompt = self.create_full_prompt(prompt, context.content)        
            response = self.llm(full_prompt)
            return response.content