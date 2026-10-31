from pathlib import Path
from tempfile import TemporaryDirectory

from faster_whisper import WhisperModel
from langchain_core.documents import Document

from app.contract import SOURCE, TYPE, LOCATION, SourceType
from app.core.config import settings
from app.core.errors import InvalidRequest, FileTooLarge


class AudioTranscriber:

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )


    def transcribe(self,filename: str, audio_data: bytes, language: str | None = None) -> list[Document]:

        if not filename:
            raise InvalidRequest("Audio filename is required")

        if not audio_data:
            raise InvalidRequest("Audio file is empty")

        if len(audio_data) > settings.max_upload_bytes:
            raise FileTooLarge("Audio file exceeds the maximum allowed size")

        extension = Path(filename).suffix.lower()

        if extension not in {".wav", ".mp3"}:
            raise InvalidRequest("Only WAV and MP3 audio files are supported")

        try:
            with TemporaryDirectory() as temp_dir:
                audio_path = Path(temp_dir) / f"audio{extension}"
                audio_path.write_bytes(audio_data)

                segments, info = self.model.transcribe(
                    str(audio_path),
                    language=language,
                    beam_size=5,
                    vad_filter=True,
                )

                documents = []

                for segment in segments:
                    text = segment.text.strip()

                    if not text:
                        continue

                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                SOURCE: filename,
                                TYPE: SourceType.AUDIO.value,
                                LOCATION: (
                                    f"{segment.start:.2f}-{segment.end:.2f} seconds"
                                ),
                                "language": info.language,
                                "start_time": segment.start,
                                "end_time": segment.end,
                            },
                        )
                    )

                if not documents:
                    raise InvalidRequest(
                        "No speech was detected in the audio file"
                    )

                return documents

        except InvalidRequest:
            raise
        except Exception as e:
            raise InvalidRequest(
                f"Audio transcription failed: {e}"
            ) from e