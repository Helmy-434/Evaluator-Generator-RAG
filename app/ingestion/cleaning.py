import re
import unicodedata

from langchain_core.documents import Document


def clean_text(text: str) -> str:
    
    if not text:
        return ""

    text = text.replace("\x00", "")

    text = unicodedata.normalize("NFKC", text)

    text = "".join(
        char
        for char in text
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_documents(documents: list[Document]) -> list[Document]:
    
    cleaned_documents = []

    for document in documents:
        cleaned_content = clean_text(document.page_content)

        if not cleaned_content:
            continue

        cleaned_documents.append(
            Document(
                page_content=cleaned_content,
                metadata=document.metadata.copy(),
            )
        )

    return cleaned_documents
