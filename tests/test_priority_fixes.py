from types import SimpleNamespace

import pytest

from app.contract import SourceType
from app.ingestion import validators
from app.workflow.evaluator_generator import run_loop
from app.agents.evaluator import EvaluationOutputError, EvaluationError


def test_audio_extensions_are_accepted():
    assert validators.validate_file("voice.wav", b"audio") is SourceType.AUDIO
    assert validators.validate_file("voice.mp3", b"audio") is SourceType.AUDIO


class FailingRetryEvaluator:
    def __init__(self):
        self.calls = 0

    def evaluate(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise EvaluationOutputError("malformed")
        raise EvaluationError("provider down")


class OneDraftGenerator:
    def generate(self, **kwargs):
        return {
            "draft_answer": "answer [Passage 1]",
            "insufficient_knowledge": False,
        }

    def build_sources(self, indices, documents):
        return []


def test_evaluator_retry_failure_returns_unvalidated_result():
    from langchain_core.documents import Document

    result = run_loop(
        "question",
        [Document(page_content="evidence", metadata={})],
        OneDraftGenerator(),
        FailingRetryEvaluator(),
    )

    assert result.validated is False
    assert result.iterations_used == 1
    assert "not validated" in result.note
