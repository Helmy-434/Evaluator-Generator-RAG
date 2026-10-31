# Evaluator-Generator RAG

An intelligent Retrieval-Augmented Generation (RAG) system that generates answers from an external knowledge base and evaluates those answers against retrieved evidence before returning them to the user.

The system combines document ingestion, vector-based retrieval, LLM generation, LLM evaluation, conversation memory, and caching to provide more reliable and context-aware responses.

---

## Table of Contents

- [Overview](#overview)
- [Main Features](#main-features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [How the System Works](#how-the-system-works)
- [Part A — Knowledge Ingestion and Infrastructure](#part-a--knowledge-ingestion-and-infrastructure)
- [Part B — Retrieval, Agents, and Workflow](#part-b--retrieval-agents-and-workflow)
- [Caching Strategy](#caching-strategy)
- [Technology Stack](#technology-stack)
- [Installation and Setup](#installation-and-setup)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Team Responsibilities](#team-responsibilities)

---

## Overview

Traditional RAG systems retrieve relevant documents and pass them directly to an LLM to generate an answer.

However, generated answers may contain:
- Incorrect information.
- Unsupported claims.
- Missing information from the knowledge base.
- Hallucinations that are not grounded in retrieved evidence.

**Evaluator-Generator RAG** addresses these challenges by introducing an evaluation stage after answer generation.

Instead of returning the first generated answer immediately, the system evaluates the answer against the retrieved context. If the answer does not satisfy the evaluation criteria, the workflow can iterate and generate an improved response.

The system is designed around two main components:

1. **Knowledge Ingestion:** Collects, validates, processes, and indexes knowledge from different sources.
2. **Evaluator-Generator Workflow:** Retrieves relevant knowledge, generates answers, evaluates them, and manages the generation process.

---

## Main Features

### Knowledge Management
- Upload documents in supported formats.
- Ingest external web pages.
- Ingest Wikipedia articles.
- Transcribe audio into text.
- Clean and normalize extracted content.
- Split documents into overlapping chunks.
- Store document embeddings in Chroma.
- Detect duplicate sources.
- List and delete ingested sources.

### Retrieval-Augmented Generation
- Semantic retrieval from the knowledge base.
- Context-aware answer generation.
- Evidence-based answer evaluation.
- Iterative answer improvement.
- Detection of insufficient knowledge.

### Intelligent Caching
- Redis-based ingestion caching.
- Answer caching.
- Corpus version tracking.
- Cache invalidation when the knowledge base changes.

### Conversation Memory
- Generator-specific memory.
- Evaluator-specific memory.
- Session-based conversation context.
- Separation of generator and evaluator memory.

### Application Interface
- Source management.
- Document ingestion.
- AI-powered chat.
- Display of generated answers and supporting sources.

---

## System Architecture

The application follows a modular architecture that separates API endpoints, ingestion, knowledge storage, retrieval, caching, agents, memory, and workflow orchestration.

```text
                         Frontend
                            |
                            v
                       FastAPI Backend
                            |
                +-----------+-----------+
                |                       |
                v                       v
          Sources API                Chat API
             (A)                       (B)
                |                       |
                v                       v
        Ingestion Pipeline          RAG Workflow
                |                       |
       +--------+--------+       +------+------+
       |        |        |       |             |
       v        v        v       v             v
     Loaders  Cleaning Chunking Retriever   Generator
       |        |        |       |             |
       +--------+--------+       |             v
                |                |          Evaluator
                v                |             |
          Chroma Vector Store <--+             |
                |                              |
                v                              v
           Redis Cache                    Memory
```

---

## Project Structure

```text
Evaluator-Generator-RAG/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── contract.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── errors.py
│   │
│   ├── api/
│   │   ├── sources.py
│   │   └── chat.py
│   │
│   ├── ingestion/
│   │   ├── validators.py
│   │   ├── file_loaders.py
│   │   ├── web_loaders.py
│   │   ├── audio_transcription.py
│   │   ├── cleaning.py
│   │   ├── chunking.py
│   │   └── pipeline.py
│   │
│   ├── knowledge/
│   │   ├── vector_store.py
│   │   └── retriever.py
│   │
│   ├── cache/
│   │   ├── redis_client.py
│   │   ├── ingestion_cache.py
│   │   └── answer_cache.py
│   │
│   ├── agents/
│   │   ├── generator.py
│   │   ├── evaluator.py
│   │   └── prompts.py
│   │
│   ├── memory/
│   │   ├── generator_memory.py
│   │   └── evaluator_memory.py
│   │
│   └── workflow/
│       ├── state.py
│       └── evaluator_generator.py
│
├── frontend/
│
├── tests/
│   ├── test_validators.py
│   ├── test_cleaning.py
│   ├── test_chunking.py
│   ├── test_web_loaders.py
│   ├── test_pipeline.py
│   ├── test_retrieval.py
│   ├── test_agents.py
│   ├── test_workflow.py
│   ├── test_memory_isolation.py
│   ├── test_cache.py
│   └── test_api.py
│
├── data/
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── README.md
```
---
## How the System Works

The system has two major workflows.

### 1. Document Ingestion Workflow

The ingestion workflow converts external information into searchable knowledge.

Supported sources include:

- PDF documents.
- DOCX documents.
- TXT documents.
- PPTX presentations.
- Source-code files.
- Web pages.
- Wikipedia articles.
- Audio files (WAV and MP3).

#### Ingestion Process

```text
                 Upload / Submit Source
                           |
                           v
                    Validate Source
                           |
                           v
                  Generate SHA-256 Hash
                           |
                           v
                 Check Redis Ingestion Cache
                           |
                    +------+------+
                    |             |
                 Cache Hit     Cache Miss
                    |             |
                    v             v
              Verify in Chroma  Check Chroma
                    |             |
                    +------+------+
                           |
                    Source Exists?
                      /       \
                    Yes        No
                    |           |
                    v           v
               Return       Load Content
               Existing         |
                                v
                         Clean Documents
                                |
                                v
                         Split into Chunks
                                |
                                v
                         Generate Chunk IDs
                                |
                                v
                         Store in Chroma
                                |
                                v
                        Increment Corpus Version
                                |
                                v
                        Save Ingestion Cache
                                |
                                v
                          Ingestion Result
```

#### Step 1: Validation

The `validators.py` module validates incoming files and URLs.

File validation includes:
- Filename validation.
- Empty-file detection.
- Maximum file-size enforcement.
- Supported-extension checking.

URL validation includes:
- HTTP/HTTPS scheme validation.
- Hostname validation.
- Rejection of local and private network destinations.
- DNS resolution checks.

#### Step 2: Source Identification

The system uses SHA-256 hashing to generate a stable source identifier.

```python
import hashlib

def generate_source_id(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
```

The resulting `source_id` identifies the source based on its content.

This supports duplicate detection and source management.

#### Step 3: Redis Cache Check

The ingestion cache checks whether the source has already been processed.

Redis key pattern:

```text
ingestion:{file_hash}
```

If Redis contains a cached source ID, the system verifies that the source still exists in Chroma.

Redis is an optimization, while Chroma remains the source of truth.

#### Step 4: Document Loading

LangChain document loaders extract text and metadata from supported formats.

| Source | Processing component |
|---|---|
| PDF | PyPDFLoader |
| DOCX | Docx2txtLoader |
| TXT | TextLoader |
| PPTX | UnstructuredPowerPointLoader |
| Code | TextLoader |
| Web | WebBaseLoader |
| Wikipedia | WikipediaLoader |
| Audio | Faster-Whisper |

The extracted content is represented using LangChain `Document` objects.

#### Step 5: Text Cleaning

The `cleaning.py` module normalizes extracted text.

Operations include:
- Unicode normalization.
- Removing null bytes.
- Removing unwanted control characters.
- Normalizing whitespace.
- Removing excessive blank lines.
- Removing empty documents.

Document metadata is preserved during cleaning.

#### Step 6: Chunking

The `chunking.py` module uses LangChain's `RecursiveCharacterTextSplitter`.

Initial configuration:

| Parameter | Value |
|---|---:|
| Chunk size | 1000 characters |
| Chunk overlap | 150 characters |

The splitter attempts to preserve natural text boundaries such as paragraphs and sentences.

Each generated chunk receives:

- `source_id`
- `chunk_id`
- `chunk_index`

Example:

```text
Source ID: abc123

Chunk 0 -> abc123:0
Chunk 1 -> abc123:1
Chunk 2 -> abc123:2
```

#### Step 7: Vector Storage

The processed chunks are stored in Chroma.

Each vector record contains:
- Chunk text.
- Embedding vector.
- Source metadata.
- Chunk identifier.
- Source location, when available.

#### Step 8: Cache Synchronization

After successful vector storage:
- The corpus version is incremented.
- The ingestion result is saved in Redis.

This allows other application components to recognize changes to the knowledge base.

---

### 2. Evaluator-Generator RAG Workflow

The second workflow handles user questions and generates evidence-based answers.

```text
                    User Question
                          |
                          v
                    Chat API
                          |
                          v
                    Answer Cache
                          |
                    +-----+-----+
                    |           |
                 Cache Hit   Cache Miss
                    |           |
                    v           v
                 Return     Retrieve Context
                 Answer          |
                                 v
                         Generator Agent
                                 |
                                 v
                         Generate Answer
                                 |
                                 v
                         Evaluator Agent
                                 |
                                 v
                        Evaluate Answer
                                 |
                      +----------+----------+
                      |                     |
                  Accepted              Rejected
                      |                     |
                      v                     v
                Final Answer        Feedback / Retry
                      |                     |
                      |              Generator Agent
                      |                     |
                      |              Evaluation Loop
                      |                     |
                      +----------+----------+
                                 |
                                 v
                          Return Response
                                 |
                                 v
                          Update Cache
```

#### Retrieval

The retriever searches the Chroma knowledge base for relevant document chunks.

It provides the generator with:
- Relevant text.
- Source information.
- Source type.
- Page or location metadata when available.

#### Generator Agent

The generator receives:
- User question.
- Retrieved context.
- Relevant conversation memory.
- Previous evaluation feedback, when applicable.

It generates an answer grounded in the retrieved information.

#### Evaluator Agent

The evaluator examines the generated answer against the available evidence.

Evaluation can consider:
- Factual correctness.
- Relevance to the question.
- Grounding in retrieved context.
- Completeness.
- Unsupported statements.

The evaluator returns feedback that can be used to improve the next generation attempt.

#### Iterative Generation

If an answer does not satisfy the evaluation criteria, the workflow can send the evaluator's feedback back to the generator.

The process continues until:
- The answer passes evaluation.
- The maximum iteration count is reached.
- The system determines that the knowledge base does not contain sufficient information.

The workflow should enforce a maximum number of iterations to prevent endless generation loops.

---

## Part A — Knowledge Ingestion and Infrastructure

Part A is responsible for the knowledge-management side of the system.

### Responsibilities

- File and URL validation.
- Document loading.
- Audio transcription.
- Text cleaning.
- Chunking.
- Ingestion pipeline.
- Chroma vector-store write operations.
- Source listing and deletion.
- Redis client and ingestion cache.
- Shared logging and application infrastructure.
- Source management API.
- Frontend integration.

### Main Modules

| Module | Responsibility |
|---|---|
| `validators.py` | Validate incoming files and URLs |
| `file_loaders.py` | Extract content from uploaded files |
| `web_loaders.py` | Load web and Wikipedia content |
| `audio_transcription.py` | Convert audio into text |
| `cleaning.py` | Normalize extracted content |
| `chunking.py` | Split documents into chunks |
| `pipeline.py` | Coordinate the complete ingestion process |
| `vector_store.py` | Add, delete, and list vector records |
| `redis_client.py` | Provide safe Redis operations |
| `ingestion_cache.py` | Cache ingestion results |
| `sources.py` | Expose source-management endpoints |

---

## Part B — Retrieval, Agents, and Workflow

Part B is responsible for the question-answering and evaluation side.

### Responsibilities

- Semantic retrieval.
- Generator agent.
- Evaluator agent.
- Prompt engineering.
- Generator memory.
- Evaluator memory.
- Answer caching.
- Workflow orchestration.
- Chat API.

### Main Modules

| Module | Responsibility |
|---|---|
| `retriever.py` | Retrieve relevant evidence from Chroma |
| `generator.py` | Generate answers from retrieved context |
| `evaluator.py` | Evaluate generated answers |
| `prompts.py` | Store agent instructions and prompts |
| `generator_memory.py` | Maintain generator conversation context |
| `evaluator_memory.py` | Maintain evaluator conversation context |
| `answer_cache.py` | Cache generated and evaluated responses |
| `state.py` | Define workflow state |
| `evaluator_generator.py` | Coordinate the generation and evaluation loop |
| `chat.py` | Expose the chat API |

---

## Shared Contracts and Metadata

The `contract.py` module defines shared constants, Pydantic models, and interfaces used by both team members.

This prevents inconsistencies between ingestion, vector storage, retrieval, and API responses.

### Source Types

The system uses a shared `SourceType` enum.

| Type | Description |
|---|---|
| `pdf` | PDF documents |
| `docx` | Word documents |
| `txt` | Text files |
| `code` | Source-code files |
| `pptx` | PowerPoint presentations |
| `web` | External web pages |
| `wikipedia` | Wikipedia articles |
| `audio` | Transcribed audio |

### Vector Metadata Contract

| Field | Description |
|---|---|
| `source_id` | Stable identifier of the entire source |
| `source` | Original filename or URL |
| `type` | Source category |
| `chunk_id` | Unique identifier for a chunk |
| `location` | Page, slide, timestamp, or line information |
| `chunk_index` | Chunk position within the source |

Example metadata:

```python
{
    "source_id": "abc123",
    "source": "python_tutorial.pdf",
    "type": "pdf",
    "chunk_id": "abc123:0",
    "chunk_index": 0,
    "location": "page 1"
}
```

The `location` field should always be a string. Use an empty string when no location is available.

### API Contracts

Shared Pydantic models include:

- `IngestUrlRequest`
- `IngestWikipediaRequest`
- `IngestResult`
- `SourceInfo`
- `SourceListResponse`
- `ChatRequest`
- `ChatResponse`
- `SourceRef`
- `ErrorResponse`

These models define the data exchanged between the frontend, API, and application components.

---

## Caching Strategy

Redis is used to reduce repeated work and improve application performance.

The system separates ingestion caching from answer caching.

### 1. Ingestion Cache

The ingestion cache prevents unnecessary processing of previously ingested content.

Redis key pattern:

```text
ingestion:{sha256_hash}
```

The cache stores the corresponding `source_id`.

Default TTL:

```text
86400 seconds (24 hours)
```

The cache checks Chroma to verify that the cached source still exists.

### 2. Answer Cache

The answer cache belongs to Part B.

It is intended to avoid repeating retrieval, generation, and evaluation for equivalent requests.

The cache should account for:
- User question.
- Relevant session or conversation context.
- Current corpus version.
- Any other inputs that affect the generated response.

### 3. Corpus Versioning

The system maintains a Redis counter:

```text
corpus:version
```

The counter represents the current knowledge-base state.

It should be incremented after successful ingestion or deletion.

The answer cache can use the corpus version to avoid returning answers generated against outdated knowledge.

### 4. Redis Resilience

The shared `RedisClient` wraps Redis operations and handles Redis errors gracefully.

Redis unavailability should not automatically prevent successful document ingestion.

However, cache synchronization failures should be logged and reported through the relevant result fields.

-
## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| FastAPI | Backend REST API |
| Pydantic | Settings and data validation |
| LangChain | Document processing and LLM integration |
| LangChain Core | Document objects and shared interfaces |
| LangChain Text Splitters | Document chunking |
| Chroma | Vector database |
| OpenAI Embeddings | Text embedding generation |
| Redis | Caching and corpus versioning |
| Faster-Whisper | Audio transcription |
| Pytest | Automated testing |
| Docker Compose | Local service orchestration |

Additional document-loading integrations are used depending on the file format.

---

## Installation and Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Evaluator-Generator-RAG
```

### 2. Create a Virtual Environment

```bash
python -m venv .env
```

Activate it on Linux:

```bash
source .env/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example configuration:

```bash
cp .env.example .env
```

Update `.env` with your API keys and application configuration.

### 5. Start Required Services

Start the services configured in Docker Compose:

```bash
docker compose up -d
```

Check running containers:

```bash
docker compose ps
```

Check Redis connectivity:

```bash
docker compose exec redis redis-cli ping
```

Expected response:

```text
PONG
```

The Redis service name may differ depending on your Docker Compose configuration.

---

## Environment Configuration

Example `.env.example`:

```env
# Application
APP_NAME=Evaluator-Generator-RAG
APP_VERSION=1.0.0
DEBUG=true

# LLM
OPENAI_API_KEY=
LLM_MODEL=
TEMPERATURE=0

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small

# Vector Database
VECTOR_PATH=./data/chroma

# Redis
REDIS_URL=redis://localhost:6379/0

# Document Processing
MAX_UPLOAD_MB=25
MAX_AUDIO_MB=50
CHUNK_SIZE=1000
CHUNK_OVERLAP=150

# Audio Transcription
WHISPER_MODEL=small
```

These are example values. Ensure that the names match the fields and environment aliases defined in `app/core/config.py`.

**Security:** Never commit your actual `.env` file or API keys to version control.

---

## Running the Application

### Start the Backend

From the project root:

```bash
uvicorn app.main:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

ReDoc documentation:

```text
http://127.0.0.1:8000/redoc
```

### Start the Frontend


```bash
python -m http.server 5173 --directory frontend```
```

## Testing

The project uses `pytest` for automated testing.

Tests should cover individual modules as well as integration between the main application components.

### Run All Tests

From the project root:

```bash
python -m pytest tests/ -v
```

### Run Individual Test Modules

```bash
python -m pytest tests/test_validators.py -v
python -m pytest tests/test_cleaning.py -v
python -m pytest tests/test_chunking.py -v
python -m pytest tests/test_web_loaders.py -v
python -m pytest tests/test_pipeline.py -v
python -m pytest tests/test_retrieval.py -v
python -m pytest tests/test_agents.py -v
python -m pytest tests/test_workflow.py -v
python -m pytest tests/test_memory_isolation.py -v
python -m pytest tests/test_cache.py -v
python -m pytest tests/test_api.py -v
```

### Test Coverage

| Test module | What it verifies |
|---|---|
| `test_validators.py` | File and URL validation |
| `test_cleaning.py` | Text normalization and metadata preservation |
| `test_chunking.py` | Chunk generation, metadata, size, and overlap |
| `test_web_loaders.py` | Web and Wikipedia loading |
| `test_pipeline.py` | Ingestion orchestration and cache interaction |
| `test_retrieval.py` | Retrieval behavior |
| `test_agents.py` | Generator and evaluator behavior |
| `test_workflow.py` | End-to-end workflow logic |
| `test_memory_isolation.py` | Generator/evaluator memory separation |
| `test_cache.py` | Redis and answer-cache behavior |
| `test_api.py` | API endpoint behavior |

### Test Samples

The chunking test suite has been executed successfully.

```text
python -m pytest tests/test_chunking.py -v

collected 6 items

test_split_documents_success              PASSED
test_split_documents_preserves_metadata   PASSED
test_split_documents_empty_input          PASSED
test_split_documents_missing_source_id    PASSED
test_split_documents_respects_chunk_size  PASSED
test_split_documents_does_not_modify_original PASSED

============================== 6 passed ==============================
```
---

## Team Responsibilities

The project is divided into two main development responsibilities.

### Part A — Ingestion, Infrastructure, and Frontend

Responsible for:
- Source validation.
- File and web loaders.
- Audio transcription.
- Text cleaning.
- Chunking.
- Ingestion pipeline.
- Chroma write operations.
- Source management.
- Redis client and ingestion cache.
- Shared logging.
- Sources API.
- Frontend implementation.

### Part B — Retrieval, Agents, and Workflow

Responsible for:
- Chroma retrieval.
- Answer caching.
- Generator agent.
- Evaluator agent.
- Agent prompts.
- Generator memory.
- Evaluator memory.
- Workflow state.
- Evaluator-generator orchestration.
- Chat API.


## License

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright 2026 Yousef Helmy & Abdelrahman Gaber

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

