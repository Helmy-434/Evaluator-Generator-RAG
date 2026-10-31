from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.contract import CHUNK_ID, SOURCE_ID
from app.core.config import settings


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "! ",
            "? ",
            "; ",
            ", ",
            " ",
            "",
        ],
        length_function=len,
        is_separator_regex=False,
    )



def split_documents(documents: list[Document], source_id: str) -> list[Document]:
    
    if not documents:
        return []

    if not source_id:
        raise ValueError("source_id is required")

    splitter = get_text_splitter()
    chunks = splitter.split_documents(documents)

    for index, chunk in enumerate(chunks):
        chunk.metadata[SOURCE_ID] = source_id
        chunk.metadata[CHUNK_ID] = f"{source_id}:{index}"
        chunk.metadata["chunk_index"] = index

    return chunks
