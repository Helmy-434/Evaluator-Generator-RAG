from types import SimpleNamespace

import pytest

from app.api import chat
from app.contract import ChatRequest, ChatResponse
from app.core.errors import NoKnowledgeLoaded
from app.knowledge.retriever import ScoredChunk


class FakeRetriever:
    def retrieve(self, question):
        return SimpleNamespace(
            chunks=[
                ScoredChunk(
                    document=SimpleNamespace(page_content="evidence", metadata={}),
                    score=0.9,
                    source_id=None,
                    location=None,
                    chunk_id=None,
                )
            ]
        )


class FakeGenerator:
    pass


class FakeEvaluator:
    pass


@pytest.mark.asyncio
async def test_chat_uses_snapshot_and_caches_validated_response(monkeypatch):
    calls = []
    response = ChatResponse(
        answer="answer",
        validated=True,
        iterations_used=1,
        insufficient_knowledge=False,
        sources=[],
    )

    monkeypatch.setattr(chat, "_components", lambda: (
        FakeRetriever(), FakeGenerator(), FakeEvaluator()
    ))
    monkeypatch.setattr(chat, "current_corpus_version", lambda: "7")
    monkeypatch.setattr(chat, "get_cached_answer", lambda question, version: None)
    monkeypatch.setattr(
        chat,
        "run_loop",
        lambda question, documents, generator, evaluator, on_event: (
            calls.append((question, documents, on_event)) or
            SimpleNamespace(
                answer=response.answer,
                validated=True,
                iterations_used=1,
                insufficient_knowledge=False,
                sources=[],
                evaluator_feedback=None,
            )
        ),
    )
    monkeypatch.setattr(
        chat,
        "cache_answer",
        lambda question, payload, version: calls.append(
            ("cache", question, payload, version)
        ) or True,
    )

    result = await chat.chat(ChatRequest(question=" q ", session_id="s1"))

    assert result == response
    assert calls[0][0] == "q"
    assert len(calls[0][1]) == 1
    assert calls[0][2] is not None
    assert calls[1][0] == "cache"
    assert calls[1][3] == "7"


@pytest.mark.asyncio
async def test_chat_returns_validated_cache_hit_without_retrieval(monkeypatch):
    cached = {
        "answer": "cached",
        "validated": True,
        "iterations_used": 1,
        "insufficient_knowledge": False,
        "sources": [],
        "evaluator_feedback": None,
        "cache_hit": False,
    }
    monkeypatch.setattr(chat, "current_corpus_version", lambda: "9")
    monkeypatch.setattr(
        chat, "get_cached_answer",
        lambda question, version: cached,
    )
    monkeypatch.setattr(
        chat,
        "_components",
        lambda: (_ for _ in ()).throw(AssertionError("cache hit called providers")),
    )

    result = await chat.chat(ChatRequest(question="q", session_id="s1"))

    assert result.answer == "cached"
    assert result.cache_hit is True


@pytest.mark.asyncio
async def test_chat_maps_empty_knowledge_base(monkeypatch):
    from app.knowledge.retriever import EmptyKnowledgeBaseError

    class EmptyRetriever:
        def retrieve(self, question):
            raise EmptyKnowledgeBaseError("empty")

    monkeypatch.setattr(chat, "_components", lambda: (
        EmptyRetriever(), FakeGenerator(), FakeEvaluator()
    ))
    monkeypatch.setattr(chat, "current_corpus_version", lambda: "0")
    monkeypatch.setattr(chat, "get_cached_answer", lambda question, version: None)

    with pytest.raises(NoKnowledgeLoaded):
        await chat.chat(ChatRequest(question="q", session_id="s1"))
