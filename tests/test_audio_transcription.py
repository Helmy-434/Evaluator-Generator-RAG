
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from app.contract import SOURCE, TYPE, LOCATION, SourceType
from app.core.config import settings
from app.core.errors import FileTooLarge, InvalidRequest
from app.ingestion import audio_transcription


@pytest.fixture
def transcriber(monkeypatch):
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            segments = [
                SimpleNamespace(
                    text=" Machine learning is useful.",
                    start=0.0,
                    end=3.5,
                ),
                SimpleNamespace(
                    text=" It helps computers learn.",
                    start=3.5,
                    end=6.0,
                ),
            ]

            info = SimpleNamespace(language="en")
            return iter(segments), info

    monkeypatch.setattr(
        audio_transcription,
        "WhisperModel",
        MockWhisperModel,
    )

    return audio_transcription.AudioTranscriber()


def test_transcribe_success(transcriber):
    documents = transcriber.transcribe(
        filename="lecture.wav",
        audio_data=b"fake audio data",
    )

    assert len(documents) == 2

    assert isinstance(documents[0], Document)
    assert documents[0].page_content == "Machine learning is useful."

    assert documents[0].metadata[SOURCE] == "lecture.wav"
    assert documents[0].metadata[TYPE] == SourceType.AUDIO.value
    assert documents[0].metadata[LOCATION] == "0.00-3.50 seconds"

    assert documents[0].metadata["language"] == "en"
    assert documents[0].metadata["start_time"] == 0.0
    assert documents[0].metadata["end_time"] == 3.5


@pytest.mark.parametrize(
    ("filename", "audio_data"),
    [
        ("", b"audio"),
        ("lecture.wav", b""),
        ("lecture.txt", b"audio"),
        ("lecture", b"audio"),
    ],
)
def test_transcribe_invalid_input(transcriber, filename, audio_data):
    with pytest.raises(InvalidRequest):
        transcriber.transcribe(filename, audio_data)


def test_transcribe_file_too_large(transcriber, monkeypatch):
    monkeypatch.setattr(settings, "max_audio_mb", 1)

    with pytest.raises(FileTooLarge):
        transcriber.transcribe(
            filename="lecture.wav",
            audio_data=b"x" * (1024 * 1024 + 1),
        )

def test_transcribe_empty_segments(monkeypatch):
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            info = SimpleNamespace(language="en")
            return iter([]), info

    monkeypatch.setattr(
        audio_transcription,
        "WhisperModel",
        MockWhisperModel,
    )

    transcriber = audio_transcription.AudioTranscriber()

    with pytest.raises(InvalidRequest, match="No speech was detected"):
        transcriber.transcribe("lecture.wav", b"fake audio")


def test_transcribe_ignores_empty_segments(monkeypatch):
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            segments = [
                SimpleNamespace(text="   ", start=0.0, end=1.0),
                SimpleNamespace(text=" Hello world ", start=1.0, end=2.0),
            ]

            info = SimpleNamespace(language="en")
            return iter(segments), info

    monkeypatch.setattr(
        audio_transcription,
        "WhisperModel",
        MockWhisperModel,
    )

    transcriber = audio_transcription.AudioTranscriber()

    documents = transcriber.transcribe("lecture.wav", b"fake audio")

    assert len(documents) == 1
    assert documents[0].page_content == "Hello world"


def test_transcribe_model_failure(monkeypatch):
    class MockWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            raise RuntimeError("Model failed")

    monkeypatch.setattr(
        audio_transcription,
        "WhisperModel",
        MockWhisperModel,
    )

    transcriber = audio_transcription.AudioTranscriber()

    with pytest.raises(InvalidRequest, match="Audio transcription failed"):
        transcriber.transcribe("lecture.wav", b"fake audio")
