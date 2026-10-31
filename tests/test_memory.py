from types import SimpleNamespace

from app.memory import evaluator_memory, generator_memory


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def get_json(self, key):
        return self.values.get(key)

    def set_json(self, key, value, ttl=None):
        self.values[key] = value
        self.ttls[key] = ttl
        return True


def test_generator_memory_appends_drafts_and_preserves_fields(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(generator_memory, "redis_client", redis)

    generator_memory.record_draft(
        "session-a",
        1,
        {
            "draft_answer": "first",
            "insufficient_knowledge": False,
            "cited_indices": [2],
            "sources": ["must not be persisted"],
        },
    )
    generator_memory.record_draft("session-a", 2, {"draft_answer": "second"})

    assert generator_memory.get_session_history("session-a") == [
        {
            "iteration": 1,
            "request_id": None,
            "draft_answer": "first",
            "insufficient_knowledge": False,
            "cited_indices": [2],
        },
        {
            "iteration": 2,
            "request_id": None,
            "draft_answer": "second",
            "insufficient_knowledge": False,
            "cited_indices": [],
        },
    ]
    assert redis.ttls["gen:session:session-a"] == generator_memory.SESSION_TTL


def test_evaluator_memory_records_evaluation_fields(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(evaluator_memory, "redis_client", redis)
    result = SimpleNamespace(
        groundedness_score=0.8,
        relevance_score=0.9,
        unsupported_claims=["claim"],
        is_valid=False,
        feedback="Revise it.",
        extra="must not be persisted",
    )

    evaluator_memory.record_evaluation("session-a", 1, result)

    assert evaluator_memory.get_session_history("session-a") == [
        {
            "iteration": 1,
            "request_id": None,
            "groundedness_score": 0.8,
            "relevance_score": 0.9,
            "unsupported_claims": ["claim"],
            "is_valid": False,
            "feedback": "Revise it.",
        }
    ]
    assert redis.ttls["eval:session:session-a"] == evaluator_memory.SESSION_TTL


def test_generator_and_evaluator_memory_are_isolated(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(generator_memory, "redis_client", redis)
    monkeypatch.setattr(evaluator_memory, "redis_client", redis)

    generator_memory.record_draft("same-session", 1, {"draft_answer": "draft"})
    evaluator_memory.record_evaluation(
        "same-session",
        1,
        SimpleNamespace(
            groundedness_score=1,
            relevance_score=1,
            unsupported_claims=[],
            is_valid=True,
            feedback=None,
        ),
    )

    assert set(redis.values) == {"gen:session:same-session", "eval:session:same-session"}
    assert generator_memory.get_session_history("same-session")[0]["draft_answer"] == "draft"
    assert evaluator_memory.get_session_history("same-session")[0]["is_valid"] is True


def test_memory_caps_history_and_clips_text(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(generator_memory, "redis_client", redis)

    for iteration in range(40):
        generator_memory.record_draft(
            "session-a",
            iteration,
            {"draft_answer": "x" * (generator_memory.MAX_DRAFT_LENGTH + 1)},
            request_id="request-a",
        )

    history = generator_memory.get_session_history("session-a")
    assert len(history) == generator_memory.MAX_HISTORY_ENTRIES
    assert history[0]["iteration"] == 8
    assert len(history[-1]["draft_answer"]) == generator_memory.MAX_DRAFT_LENGTH
    assert history[-1]["request_id"] == "request-a"


def test_memory_read_failure_degrades_to_empty_history(monkeypatch):
    class BrokenRedis:
        def get_json(self, key):
            raise RuntimeError("redis down")

    monkeypatch.setattr(generator_memory, "redis_client", BrokenRedis())
    monkeypatch.setattr(evaluator_memory, "redis_client", BrokenRedis())

    assert generator_memory.get_session_history("session-a") == []
    assert evaluator_memory.get_session_history("session-a") == []
