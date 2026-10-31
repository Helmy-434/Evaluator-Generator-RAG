from __future__ import annotations

import re
from langchain_core.documents import Document
from app.contract import SOURCE, LOCATION

TAG_SANITIZE_RE = re.compile(
    r"<\s*/?\s*(context|draft_answer|previous_draft|evaluator_feedback)\b[^>]*>",
    re.IGNORECASE,
)


def escape_xml_delimiters(text: str) -> str:
    return TAG_SANITIZE_RE.sub(
        lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), text or ""
    )


def format_context(documents: list[Document]) -> str:
    blocks = []
    for idx, doc in enumerate(documents, start=1):
        meta = doc.metadata or {}
        src = meta.get(SOURCE, "unknown")
        loc = meta.get(LOCATION)
        loc_str = f", Location: {loc}" if loc else ""
        header = escape_xml_delimiters(f"[Passage {idx} | Source: {src}{loc_str}]")
        blocks.append(f"{header}\n{escape_xml_delimiters(doc.page_content.strip())}")
    return "\n\n".join(blocks)