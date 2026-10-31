import hashlib
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

import app.contract as contract
from app.knowledge import vector_store as vs


class FakeEmbeddings(Embeddings):
    def _vec(self, text):
        return [b / 255 for b in hashlib.sha256(text.encode()).digest()[:16]]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, "get_embeddings", lambda: FakeEmbeddings())
    monkeypatch.setattr(contract, "VECTOR_DIR", str(tmp_path))
    monkeypatch.setattr(vs.redis_client, "incr", lambda key: 1)   # no Redis needed
    contract.get_vector_store.cache_clear()
    yield
    contract.get_vector_store.cache_clear()


def make_chunks(source_id="abc", n=3, location=""):
    return [
        Document(
            page_content=f"chunk {i}",
            metadata={
                "source_id": source_id, "source": "a.txt", "type": "txt",
                "chunk_id": f"{source_id}:{i}", "location": location,
                "junk": ["not", "allowed"],          # must be dropped
            },
        )
        for i in range(n)
    ]


def test_add_and_list():
    count, version = vs.add_chunks(make_chunks())
    assert (count, version) == (3, "1")
    sources = vs.list_sources()
    assert len(sources) == 1 and sources[0].chunk_count == 3


def test_same_chunks_twice_do_not_duplicate():
    vs.add_chunks(make_chunks())
    vs.add_chunks(make_chunks())
    assert vs.list_sources()[0].chunk_count == 3


def test_delete_source():
    vs.add_chunks(make_chunks())
    deleted, _ = vs.delete_source("abc")
    assert deleted == 3
    assert not vs.source_exists("abc")
    assert vs.list_sources() == []


def test_replace_source_shrinks():
    vs.add_chunks(make_chunks(n=5))
    vs.replace_source("abc", make_chunks(n=2))
    assert vs.list_sources()[0].chunk_count == 2


def test_none_location_is_accepted():
    chunks = make_chunks()
    chunks[0].metadata["location"] = None
    vs.add_chunks(chunks)                              # must not raise


def test_empty_list():
    assert vs.add_chunks([]) == (0, None)


def test_missing_chunk_id_raises():
    bad = [Document(page_content="x", metadata={"source_id": "abc"})]
    with pytest.raises(ValueError):
        vs.add_chunks(bad)