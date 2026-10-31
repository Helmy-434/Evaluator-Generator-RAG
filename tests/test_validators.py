
import pytest

from app.contract import SourceType
from app.core.errors import InvalidRequest, FileTooLarge
from app.core.config import settings
from app.ingestion.validators import validate_file


@pytest.mark.parametrize(
    "filename, expected_type",
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


def test_validate_file_missing_filename():
    with pytest.raises(InvalidRequest):
        validate_file("", b"Some content")


def test_validate_file_empty_content():
    with pytest.raises(InvalidRequest):
        validate_file("document.pdf", b"")


def test_validate_file_unsupported_extension():
    with pytest.raises(InvalidRequest):
        validate_file("document.exe", b"Some content")


def test_validate_file_without_extension():
    with pytest.raises(InvalidRequest):
        validate_file("document", b"Some content")


def test_validate_file_too_large(monkeypatch):
    # Set maximum upload size to 1 MB for this test.
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    data = b"x" * (1024 * 1024 + 1)

    with pytest.raises(FileTooLarge):
        validate_file("document.pdf", data)


def test_validate_file_exact_maximum_size(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    data = b"x" * (1024 * 1024)

    result = validate_file("document.pdf", data)

    assert result == SourceType.PDF
