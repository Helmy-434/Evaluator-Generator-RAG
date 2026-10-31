from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from app.contract import EVALUATOR_API_KEY, EVALUATOR_MODEL, EVALUATOR_TIMEOUT
from app.agents.prompts import EVALUATOR_SYSTEM_PROMPT
from app.agents.context_formatter import format_context, escape_xml_delimiters

logger = logging.getLogger(__name__)

APPROVAL_THRESHOLD = 0.85
_EMPTY_CLAIMS = {"none", "n/a", "no unsupported claims", "[]"}


class EvaluationError(Exception):
    """Provider/network failure: the loop should degrade (validated=False)."""


class EvaluationOutputError(EvaluationError):
    """Model answered but output is unusable (None, scale error): retry once."""


class LLMEvaluationOutput(BaseModel):
    groundedness_score: float = Field(description="0.0 to 1.0. 1.0 = every claim backed by context.")
    relevance_score: float = Field(description="0.0 to 1.0. 1.0 = fully answers the question from the context.")
    unsupported_claims: list[str] = Field(default_factory=list,
        description="Specific claims in the draft NOT supported by the context. Empty list if none.")
    refused_but_answerable: bool = Field(default=False,
        description="True only if the draft refused to answer but the context actually contains the answer.")
    critique: str = Field(default="",
        description="Short, actionable feedback if anything is wrong. Empty string if the draft is fine.")


class EvaluationResult(BaseModel):
    groundedness_score: float
    relevance_score: float
    unsupported_claims: list[str]
    is_valid: bool
    feedback: str | None = None


class Evaluator:
    def __init__(self, llm: ChatGoogleGenerativeAI | None = None):
        if not llm and not EVALUATOR_API_KEY:
            raise ValueError("EVALUATOR_API_KEY is not set (add it to .env).")
        self.llm = llm or ChatGoogleGenerativeAI(
            model=EVALUATOR_MODEL,
            google_api_key=EVALUATOR_API_KEY,
            timeout=EVALUATOR_TIMEOUT,
            temperature=0.0,  
        )
        self.structured_llm = self.llm.with_structured_output(LLMEvaluationOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", EVALUATOR_SYSTEM_PROMPT),
            ("user",
             "<context>\n{context}\n</context>\n\n"
             "Question: {question}\n\n"
             "<draft_answer>\n{draft_answer}\n</draft_answer>\n\n"
             "Refusal Flag: {refusal_flag}\n\n"
             "Instruction: Evaluate <draft_answer> against <context> using the rubric."),
        ])
        self.chain = self.prompt | self.structured_llm

    @staticmethod
    def _check_score(score: float, name: str) -> float:
        if not (0.0 <= score <= 1.0):
            raise EvaluationOutputError(f"{name} out of range: {score}")
        return score

    def evaluate(self, question: str, documents: list[Document], draft_answer: str,
                 insufficient_knowledge: bool = False) -> EvaluationResult:
        if not documents:
            if insufficient_knowledge:
                return EvaluationResult(groundedness_score=1.0, relevance_score=1.0,
                                        unsupported_claims=[], is_valid=True)
            return EvaluationResult(
                groundedness_score=0.0, relevance_score=0.0,
                unsupported_claims=["Answer generated with no supporting context."],
                is_valid=False,
                feedback="No context was retrieved to support any factual assertions.")

        refusal_flag = (
            "Draft states insufficient knowledge (refusal). Check if the context contains the answer."
            if insufficient_knowledge else "Draft claims to answer the question.")
        try:
            out = self.chain.invoke({
                "context": format_context(documents),
                "question": escape_xml_delimiters(question),
                "draft_answer": escape_xml_delimiters(draft_answer),
                "refusal_flag": refusal_flag,
            })
        except Exception as exc:
            logger.error("Evaluator call failed: %s", exc, exc_info=True)
            raise EvaluationError(f"Evaluator LLM call failed: {exc}") from exc

        if out is None:
            raise EvaluationOutputError("Evaluator returned null structured output.")

        g = self._check_score(out.groundedness_score, "groundedness_score")
        r = self._check_score(out.relevance_score, "relevance_score")
        claims = [c.strip() for c in out.unsupported_claims
                  if c and c.strip() and c.strip().lower() not in _EMPTY_CLAIMS]
        lazy = insufficient_knowledge and out.refused_but_answerable

        valid = g >= APPROVAL_THRESHOLD and r >= APPROVAL_THRESHOLD and not claims and not lazy
        if valid:
            return EvaluationResult(groundedness_score=g, relevance_score=r,
                                    unsupported_claims=[], is_valid=True)

        parts: list[str] = []
        if lazy:
            parts.append("The context contains the answer. Answer the question with [Passage N] citations instead of refusing.")
        if claims:
            parts.append("Remove or correct these unsupported claims: " + "; ".join(claims))
        if r < APPROVAL_THRESHOLD and not lazy:
            parts.append("Address the question more directly using only the context.")
        if out.critique.strip():
            parts.append(out.critique.strip())
        return EvaluationResult(groundedness_score=g, relevance_score=r,
                                unsupported_claims=claims, is_valid=False,
                                feedback=" ".join(parts))