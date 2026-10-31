
import socket

import pytest

from app.core.contract import SourceType
from app.core.config import settings
from app.core.errors import FileTooLarge, InvalidRequest
from app.ingestion.validators import validate_file, validate_url


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("document.pdf", SourceType.PDF),
        ("document.docx", SourceType.DOCX),
        ("document.txt", SourceType.TXT),
        ("presentation.pptx", SourceType.PPTX),
        ("DOCUMENT.PDF", SourceType.PDF),
    ],
)
def test_validate_file_success(filename, expected_type):
    result = validate_file(filename, b"Valid file content")

    assert result == expected_type


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("", b"Some content"),
        ("document.pdf", b""),
        ("document.exe", b"Some content"),
        ("document", b"Some content"),
    ],
)
def test_validate_file_invalid_input(filename, content):
    with pytest.raises(InvalidRequest):
        validate_file(filename, content)


@pytest.mark.parametrize(
    ("max_size", "data_size", "should_fail"),
    [
        (1, 1024 * 1024 + 1, True),
        (1, 1024 * 1024, False),
    ],
)
def test_validate_file_size(monkeypatch, max_size, data_size, should_fail):
    monkeypatch.setattr(settings, "max_upload_mb", max_size)
    data = b"x" * data_size

    if should_fail:
        with pytest.raises(FileTooLarge):
            validate_file("document.pdf", data)
    else:
        assert validate_file("document.pdf", data) == SourceType.PDF


@pytest.mark.parametrize(
    "scheme",
    ["https", "http"],
)
def test_validate_url_success(monkeypatch, scheme):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    url = f"{scheme}://example.com"

    assert validate_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "ftp://example.com",
        "file:///etc/passwd",
        "example.com",
        "http://",
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://192.168.1.1",
        "http://10.0.0.1",
        "http://169.254.169.254",
        "http://internal.local",
        "http://service.internal",
        "http://user:password@example.com",
    ],
)
def test_validate_url_invalid_input(url):
    with pytest.raises(InvalidRequest):
        validate_url(url)


def test_validate_url_rejects_private_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443))
        ],
    )

    with pytest.raises(InvalidRequest):
        validate_url("https://example.com")


def test_validate_url_rejects_mixed_public_and_private_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443)),
        ],
    )

    with pytest.raises(InvalidRequest):
        validate_url("https://example.com")


def test_validate_url_rejects_dns_failure(monkeypatch):
    def raise_dns_error(*args, **kwargs):
        raise socket.gaierror("DNS resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", raise_dns_error)

    with pytest.raises(InvalidRequest):
        validate_url("https://unknown-example.com")


def test_validate_url_rejects_long_url():
    url = "https://example.com/" + ("a" * 2048)

    with pytest.raises(InvalidRequest):
        validate_url(url)
