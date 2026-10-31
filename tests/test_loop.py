import pytest
from langchain_core.documents import Document

from app.agents.evaluator import EvaluationResult, EvaluationError
from app.agents.generator import GenerationError
from app.agents.prompts import REFUSAL_SENTENCE
from app.workflow.evaluator_generator import run_loop

DOCS = [Document(page_content="t", metadata={"source": "a.txt", "type": "txt", "location": ""})]


class FakeGen:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []
    def generate(self, **kw):
        self.calls.append(kw)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return {"draft_answer": a, "insufficient_knowledge": a == REFUSAL_SENTENCE, "sources": []}
    def build_sources(self, idx, docs): return [docs[i - 1] for i in idx]


class FakeEval:
    def __init__(self, results):
        self.results = list(results)
    def evaluate(self, **kw):
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def verdict(valid, fb=None):
    return EvaluationResult(groundedness_score=1.0 if valid else 0.5, relevance_score=1.0,
                            unsupported_claims=[], is_valid=valid, feedback=fb)


def test_approved_first_try():
    r = run_loop("q", DOCS, FakeGen(["A [Passage 1]"]), FakeEval([verdict(True)]))
    assert r.validated and r.iterations_used == 1 and r.answer == "A [1]"

def test_feedback_reaches_generator_and_second_pass_approves():
    g = FakeGen(["bad", "good [Passage 1]"])
    r = run_loop("q", DOCS, g, FakeEval([verdict(False, "fix X"), verdict(True)]))
    assert r.validated and r.iterations_used == 2
    assert g.calls[1]["evaluator_feedback"] == "fix X" and g.calls[1]["previous_draft"] == "bad"

def test_cap_returns_latest_unvalidated():
    g = FakeGen(["d1", "d2", "d3", "d4"])
    r = run_loop("q", DOCS, g, FakeEval([verdict(False, "f")] * 4))
    assert not r.validated and r.iterations_used == 4 and r.answer.startswith("d4") and not g.answers

def test_empty_feedback_does_not_crash():
    g = FakeGen(["d1", "d2"])
    r = run_loop("q", DOCS, g, FakeEval([verdict(False, ""), verdict(True)]))
    assert r.validated and g.calls[1]["evaluator_feedback"]

def test_no_documents_refuses_without_llm():
    g = FakeGen([])
    r = run_loop("q", [], g, FakeEval([]))
    assert r.insufficient_knowledge and r.validated and r.iterations_used == 0 and not g.calls

def test_evaluator_outage_degrades():
    r = run_loop("q", DOCS, FakeGen(["A"]), FakeEval([EvaluationError("down")]))
    assert not r.validated and "unavailable" in r.note

def test_generator_retry_once_then_raise():
    with pytest.raises(GenerationError):
        run_loop("q", DOCS, FakeGen([GenerationError("x"), GenerationError("x")]), FakeEval([]))

def test_generator_failure_after_first_pass_returns_previous():
    g = FakeGen(["d1", GenerationError("x"), GenerationError("x")])
    r = run_loop("q", DOCS, g, FakeEval([verdict(False, "f")]))
    assert not r.validated and r.answer.startswith("d1")