import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, sources
from app.cache.redis_client import redis_client
from app.core.config import settings
from app.core.errors import register_error_handlers

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

app = FastAPI(title="Evaluator-Generator RAG", version="0.1.0")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)


# routers
app.include_router(sources.router, prefix="/api")
app.include_router(chat.router, prefix="/api")




@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "redis": redis_client.ping()}