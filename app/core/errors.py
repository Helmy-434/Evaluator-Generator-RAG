from __future__ import annotations

import logging
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.contract import ErrorResponse

log = logging.getLogger(__name__)


class ErrorCode(str, Enum):

    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_DOCUMENT = "empty_document"
    INVALID_URL = "invalid_url"
    INVALID_REQUEST = "invalid_request"
    VALIDATION_ERROR = "validation_error"
    SOURCE_NOT_FOUND = "source_not_found"
    FETCH_FAILED = "fetch_failed"
    TRANSCRIPTION_FAILED = "transcription_failed"
    INGESTION_FAILED = "ingestion_failed"
    NO_KNOWLEDGE_LOADED = "no_knowledge_loaded"
    CHAT_UNAVAILABLE = "chat_unavailable"
    INTERNAL_ERROR = "internal_error"


class AppError(Exception):
    """Base class: carries an error code, an HTTP status and a human-readable message."""
    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message or self.code.value


# --- Ingestion / sources errors (raised by validators, loaders, pipeline, API) --------------
class UnsupportedFileType(AppError):
    code = ErrorCode.UNSUPPORTED_FILE_TYPE
    status_code = 415


class FileTooLarge(AppError):
    code = ErrorCode.FILE_TOO_LARGE
    status_code = 413


class EmptyDocument(AppError):
    code = ErrorCode.EMPTY_DOCUMENT
    status_code = 422


class InvalidURL(AppError):
    code = ErrorCode.INVALID_URL
    status_code = 422


class InvalidRequest(AppError):
    code = ErrorCode.INVALID_REQUEST
    status_code = 422


class SourceNotFound(AppError):
    code = ErrorCode.SOURCE_NOT_FOUND
    status_code = 404


class FetchFailed(AppError):
    """A web page / Wikipedia page could not be downloaded."""
    code = ErrorCode.FETCH_FAILED
    status_code = 502


class TranscriptionFailed(AppError):
    code = ErrorCode.TRANSCRIPTION_FAILED
    status_code = 422


class IngestionFailed(AppError):
    code = ErrorCode.INGESTION_FAILED
    status_code = 500


# --- Chat errors (used by the chat side) -------------------------------------------------
class NoKnowledgeLoaded(AppError):
    code = ErrorCode.NO_KNOWLEDGE_LOADED
    status_code = 409


class ChatUnavailable(AppError):
    code = ErrorCode.CHAT_UNAVAILABLE
    status_code = 502


# --- FastAPI wiring -------------------------------------------------------------------------
def _json(status_code: int, error: str, detail: str) -> JSONResponse:
    body = ErrorResponse(error=error, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        log.warning("%s: %s", exc.code.value, exc.message)
        return _json(exc.status_code, exc.code.value, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return _json(422, ErrorCode.VALIDATION_ERROR.value, problems)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return _json(500, ErrorCode.INTERNAL_ERROR.value, "Unexpected server error")