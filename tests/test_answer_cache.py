from app.cache import answer_cache


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get_json(self, key):
        return self.values.get(key)

    def set_json(self, key, value, ttl=None):
        self.values[key] = value
        return True


def test_cache_uses_explicit_corpus_snapshot_for_read_and_write(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(answer_cache, "redis_client", redis)
    response = {"answer": "grounded", "validated": True}

    assert answer_cache.cache_answer("a  b", response, "7")
    assert answer_cache.get_cached_answer(" a b ", "7") == response
    assert answer_cache.get_cached_answer("a b", "8") is None


def test_cache_rejects_unvalidated_answers(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(answer_cache, "redis_client", redis)

    assert not answer_cache.cache_answer("question", {"validated": False}, "7")
    assert redis.values == {}


def test_cache_key_changes_when_model_or_prompt_changes():
    base = answer_cache._answer_key("question", "7")
    assert answer_cache._answer_key(
        "question", "7", generator_model="different"
    ) != base
    assert answer_cache._answer_key(
        "question", "7", prompt_version="v2"
    ) != base


def test_cache_redis_failures_degrade_to_misses(monkeypatch):
    class BrokenRedis:
        def get_json(self, key):
            raise RuntimeError("redis down")

        def set_json(self, key, value, ttl=None):
            raise RuntimeError("redis down")

    monkeypatch.setattr(answer_cache, "redis_client", BrokenRedis())
    assert answer_cache.get_cached_answer("question", "7") is None
    assert not answer_cache.cache_answer(
        "question", {"validated": True}, "7"
    )
