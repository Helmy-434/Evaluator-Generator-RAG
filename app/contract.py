from __future__ import annotations

import os
from enum import Enum

from pydantic import BaseModel, Field

# =============================================================================
# 1. CHUNK FORMAT: every chunk is a langchain Document with these metadata keys
# =============================================================================
class SourceType(str, Enum):
    PDF = "pdf"; DOCX = "docx"; TXT = "txt"; CODE = "code"; PPTX = "pptx"
    WEB = "web"; WIKIPEDIA = "wikipedia"; AUDIO = "audio"

SOURCE_ID = "source_id"      # str  stable id of the whole source (hash of its content)
SOURCE = "source"            # str  filename or URL shown to the user
TYPE = "type"                # str  a SourceType value
CHUNK_ID = "chunk_id"        # str  f"{source_id}:{chunk_index}"
LOCATION = "location"        # str|None  "page 3" | "slide 5" | "00:01:23" | "lines 10-42"
# page_content = the chunk text. Nothing else is guaranteed.

# =============================================================================
# 2. SHARED STORAGE: both sides open the SAME store with the SAME embeddings
#    (different embedding models silently give garbage retrieval)
# =============================================================================
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
VECTOR_DIR = os.getenv("VECTOR_DIR", "./data/vectorstore")
COLLECTION = "knowledge"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def get_embeddings():
    from langchain_openai import OpenAIEmbeddings   # change provider HERE only
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)

def get_vector_store():
    """Ingestion calls .add_documents()/.delete(); chat calls .as_retriever()/similarity search."""
    from langchain_chroma import Chroma
    return Chroma(collection_name=COLLECTION, embedding_function=get_embeddings(),
                  persist_directory=VECTOR_DIR)

# =============================================================================
# 3. CORPUS VERSION: how chat knows its cached answers are stale
#    Ingestion calls bump_corpus_version() after EVERY add or delete.
#    Chat includes get_corpus_version() in every answer-cache key.
# =============================================================================
CORPUS_VERSION_KEY = "corpus:version"

def bump_corpus_version(redis_client) -> str:
    return str(redis_client.incr(CORPUS_VERSION_KEY))

def get_corpus_version(redis_client) -> str:
    return redis_client.get(CORPUS_VERSION_KEY) or "0"   # chat must treat Redis errors as "0"/no cache

# =============================================================================
# 4. REDIS KEY NAMESPACES (so nothing collides)
#    ingest:*  -> ingestion (doc hashes, embedding cache)
#    answer:*  -> chat (final answers, evaluations)
#    gen:*     -> Generator memory      (never touched by evaluator code)
#    eval:*    -> Evaluator memory      (never touched by generator code)
# =============================================================================
NS_INGEST, NS_ANSWER, NS_GEN_MEMORY, NS_EVAL_MEMORY = "ingest", "answer", "gen", "eval"

# =============================================================================
# 5. HTTP API between frontend and backend
#    POST   /api/sources/files        multipart "file"        -> IngestResult
#    POST   /api/sources/url          {url}                   -> IngestResult
#    POST   /api/sources/wikipedia    {page, lang="en"}       -> IngestResult
#    GET    /api/sources                                      -> SourceListResponse
#    DELETE /api/sources/{source_id}                          -> SourceListResponse
#    POST   /api/chat                 ChatRequest             -> ChatResponse
#    Errors: HTTP 4xx/5xx with ErrorResponse body.
# =============================================================================
class IngestUrlRequest(BaseModel):
    url: str

class IngestWikipediaRequest(BaseModel):
    page: str
    lang: str = "en"

class IngestResult(BaseModel):
    source_id: str
    source: str
    type: SourceType
    status: str                    # "ingested" | "already_exists" | "failed"
    chunks_added: int = 0
    message: str | None = None     # reason when failed / skipped

class SourceInfo(BaseModel):
    source_id: str
    source: str
    type: SourceType
    chunk_count: int

class SourceListResponse(BaseModel):
    sources: list[SourceInfo]

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str

class SourceRef(BaseModel):
    source: str
    type: SourceType
    location: str | None = None
    snippet: str = ""

class ChatResponse(BaseModel):
    answer: str
    validated: bool                # False => loop hit the cap of 4 without approval
    iterations_used: int           # 0 = served from cache or "not in sources" short-circuit
    insufficient_knowledge: bool = False
    sources: list[SourceRef] = []
    evaluator_feedback: str | None = None
    cache_hit: bool = False

class ErrorResponse(BaseModel):
    error: str                     # e.g. "unsupported_file_type", "no_knowledge_loaded"
    detail: str