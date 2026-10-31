from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app.agents.citations import is_refusal_answer, cited_indices, renumber_citations
from app.agents.prompts import REFUSAL_SENTENCE
from app.agents.evaluator import (Evaluator, LLMEvaluationOutput,
                                  EvaluationError, EvaluationOutputError)
from app.agents.generator import Generator
from app.core.contract import SOURCE, TYPE, LOCATION


class FakeStructuredLLM:
    def __init__(self, out): self.out = out
    def with_structured_output(self, schema, **kw):
        return RunnableLambda(lambda _: self.out)


def docs(n=3):
    return [Document(page_content=f"text {i}",
                     metadata={SOURCE: f"f{i}.txt", TYPE: "txt", LOCATION: ""})
            for i in range(1, n + 1)]


def ev(out):
    return Evaluator(llm=FakeStructuredLLM(out))


# ---- refusal ----
def test_refusal_variants():
    s = REFUSAL_SENTENCE
    for v in [s, s.lower(), f'"{s}"', f'“{s}”', f'"{s[:-1]}".', f"Answer: {s}", s + "  "]:
        assert is_refusal_answer(v), v

def test_partial_answer_is_not_refusal():
    assert not is_refusal_answer(REFUSAL_SENTENCE + " However X is Y [Passage 2].")


# ---- citations ----
def test_header_numbers_not_captured():
    assert cited_indices("[Passage 1 | Source: report2.pdf, Location: page 3]", 5) == [1]

def test_list_range_and_repeated_forms():
    assert cited_indices("a [Passage 1, Passage 2] b [Passages 4-5]", 5) == [1, 2, 4, 5]

def test_huge_range_is_clamped_fast():
    assert cited_indices("[Passage 1-999999999]", 3) == [1, 2, 3]

def test_out_of_range_dropped():
    assert cited_indices("[Passage 9]", 3) == []

def test_renumber():
    txt, order = renumber_citations("A [Passage 3]. B [Passage 1, 3].", 3)
    assert order == [3, 1] and txt == "A [1]. B [1, 2]."


# ---- generator ----
def gen(answer):
    return Generator(llm=RunnableLambda(lambda _: answer))

def test_generator_refusal_has_no_sources():
    r = gen(REFUSAL_SENTENCE).generate("q", docs())
    assert r["insufficient_knowledge"] and r["sources"] == []

def test_generator_returns_only_cited_sources():
    r = gen("Fact [Passage 2].").generate("q", docs())
    assert [s.source for s in r["sources"]] == ["f2.txt"]


# ---- evaluator ----
def base(**kw):
    d = dict(groundedness_score=1.0, relevance_score=1.0, unsupported_claims=[],
             refused_but_answerable=False, critique="")
    d.update(kw); return LLMEvaluationOutput(**d)

def test_good_answer_approved():
    assert ev(base()).evaluate("q", docs(), "a [Passage 1]").is_valid

def test_unsupported_claim_rejected_with_feedback():
    r = ev(base(unsupported_claims=["X"])).evaluate("q", docs(), "a")
    assert not r.is_valid and "X" in r.feedback

def test_none_claim_filler_ignored():
    assert ev(base(unsupported_claims=["", "None"])).evaluate("q", docs(), "a").is_valid

def test_scale_error_raises_output_error():
    try:
        ev(base(groundedness_score=7.5)).evaluate("q", docs(), "a")
        assert False
    except EvaluationOutputError:
        pass

def test_none_output_raises():
    try:
        ev(None).evaluate("q", docs(), "a")
        assert False
    except EvaluationOutputError:
        pass

def test_lazy_refusal_rejected_without_fake_claim():
    r = ev(base(relevance_score=0.0, refused_but_answerable=True)).evaluate(
        "q", docs(), REFUSAL_SENTENCE, insufficient_knowledge=True)
    assert not r.is_valid and r.unsupported_claims == [] and "answer" in r.feedback.lower()

def test_correct_refusal_approved():
    assert ev(base()).evaluate("q", docs(), REFUSAL_SENTENCE, insufficient_knowledge=True).is_valid

def test_provider_failure_is_plain_evaluation_error():
    class Boom:
        def with_structured_output(self, s, **kw):
            return RunnableLambda(lambda _: (_ for _ in ()).throw(RuntimeError("down")))
    try:
        Evaluator(llm=Boom()).evaluate("q", docs(), "a")
        assert False
    except EvaluationError as e:
        assert not isinstance(e, EvaluationOutputError)