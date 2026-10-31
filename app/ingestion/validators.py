from pathlib import Path

from app.contract import SourceType
from app.core.config import settings
from app.core.errors import InvalidRequest, FileTooLarge


SUPPORTED_FILE_TYPES = {
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
    ".txt": SourceType.TXT,
    ".pptx": SourceType.PPTX,
}


def validate_file(filename: str, data: bytes) -> SourceType:

    if not filename:
        raise InvalidRequest("Filename is missing")

    if not data:
        raise InvalidRequest("File is empty")

    if len(data) > settings.max_upload_bytes:
        raise FileTooLarge("File exceeds maximum upload size")

    extension = Path(filename).suffix.lower()

    source_type = SUPPORTED_FILE_TYPES.get(extension)

    if source_type is None:
        supported = ", ".join(SUPPORTED_FILE_TYPES)
        raise InvalidRequest(
            f"Unsupported file extension: {extension}. "
            f"Supported extensions: {supported}"
        )

    return source_type