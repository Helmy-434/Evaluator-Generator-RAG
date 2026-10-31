from pathlib import Path

from app.contract import SourceType
from app.core.config import settings
from app.core.errors import InvalidRequest, FileTooLarge

import ipaddress
import socket
from urllib.parse import urlsplit


SUPPORTED_FILE_TYPES = {
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
    ".txt": SourceType.TXT,
    ".pptx": SourceType.PPTX,
    ".wav": SourceType.AUDIO,
    ".mp3": SourceType.AUDIO,

    ".py": SourceType.CODE,
    ".js": SourceType.CODE,
    ".ts": SourceType.CODE,
    ".java": SourceType.CODE,
    ".cpp": SourceType.CODE,
    ".c": SourceType.CODE,
    ".h": SourceType.CODE,
    ".html": SourceType.CODE,
    ".css": SourceType.CODE,
    ".sql": SourceType.CODE,
    ".json": SourceType.CODE,
    ".yaml": SourceType.CODE,
    ".yml": SourceType.CODE,
    ".sh": SourceType.CODE,
}


def validate_file(filename: str, data: bytes) -> SourceType:

    if not filename:
        raise InvalidRequest("Filename is missing")

    if not data:
        raise InvalidRequest("File is empty")

    extension = Path(filename).suffix.lower()

    source_type = SUPPORTED_FILE_TYPES.get(extension)

    if source_type is None:
        supported = ", ".join(SUPPORTED_FILE_TYPES)
        raise InvalidRequest(
            f"Unsupported file extension: {extension}. "
            f"Supported extensions: {supported}"
        )

    max_bytes = (
        settings.max_audio_bytes
        if source_type is SourceType.AUDIO
        else settings.max_upload_bytes
    )
    if len(data) > max_bytes:
        raise FileTooLarge("File exceeds maximum allowed size")

    return source_type





def validate_url(url: str) -> str:
    
    if not url or not url.strip():
        raise InvalidRequest("URL is required")

    url = url.strip()

    if len(url) > 2048:
        raise InvalidRequest("URL is too long")

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise InvalidRequest("Invalid URL") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidRequest("Only HTTP and HTTPS URLs are supported")

    if not hostname:
        raise InvalidRequest("URL must contain a hostname")

    if parsed.username or parsed.password:
        raise InvalidRequest("URLs containing credentials are not allowed")

    hostname = hostname.rstrip(".").lower()

    if (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
    ):
        raise InvalidRequest("Local and internal addresses are not allowed")

    try:
        ip = ipaddress.ip_address(hostname)

        if not ip.is_global:
            raise InvalidRequest("Private or reserved IP addresses are not allowed")

    except ValueError:
        try:
            addresses = socket.getaddrinfo(
                hostname,
                port or (443 if parsed.scheme.lower() == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise InvalidRequest("Could not resolve URL hostname") from exc

        for address in addresses:
            resolved_ip = ipaddress.ip_address(address[4][0])

            if not resolved_ip.is_global:
                raise InvalidRequest(
                    "URL resolves to a private or reserved IP address"
                )

    return url