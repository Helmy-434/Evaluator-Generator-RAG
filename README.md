**Project Structure**

```text
project/
├── app/
│   ├── main.py                       # Application entry point
│   ├── core/                         # Shared infrastructure
│   │   ├── config.py                 # Environment variables and settings
│   │   ├── logging.py                # Logging configuration
│   │   └── errors.py                 # Shared error handling
│   ├── schemas.py                    # Shared Pydantic contracts
│   │
│   ├── api/
│   │   ├── sources.py                # Source API
│   │   └── chat.py                   # AI chat API
│   │
│   ├── ingestion/                    # Knowledge ingestion
│   │   ├── validators.py             # File and URL validation
│   │   ├── file_loaders.py           # PDF, DOCX, TXT, code, PPT/PPTX
│   │   ├── web_loaders.py            # Web pages and Wikipedia
│   │   ├── audio_transcription.py    # WAV -> text
│   │   ├── cleaning.py               # Extracted-text cleanup
│   │   ├── chunking.py               # Split documents into chunks
│   │   └── pipeline.py               # Load -> clean -> chunk -> index
│   │
│   ├── knowledge/
│   │   ├── vector_store.py           # Vector storage and indexing
│   │   └── retriever.py              # Retrieve relevant evidence
│   │
│   ├── cache/
│   │   ├── redis_client.py           # Shared Redis wrapper
│   │   ├── ingestion_cache.py        # Document/embedding cache
│   │   └── answer_cache.py           # Answer and evaluation cache
│   │
│   ├── agents/
│   │   ├── generator.py              # Generator LLM
│   │   ├── evaluator.py              # Evaluator LLM
│   │   └── prompts.py                # Agent prompts
│   │
│   ├── memory/
│   │   ├── generator_memory.py       # Generator memory
│   │   └── evaluator_memory.py       # Evaluator memory
│   │
│   └── workflow/
│       ├── state.py                  # Workflow state
│       └── evaluator_generator.py    # LCEL workflow
│
├── frontend/                         # Frontend application
├── tests/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_agents.py
│   ├── test_workflow.py
│   ├── test_memory_isolation.py
│   ├── test_cache.py
│   └── test_api.py
│
├── docker-compose.yml
├── .env.example
└── requirements.txt
```
