from __future__ import annotations

import logging
import re

from app.agents.prompts import REFUSAL_SENTENCE

logger = logging.getLogger(__name__)

BRACKET_RE = re.compile(r"\[\s*Passages?\b([^\]]*)\]", re.IGNORECASE)
NUM_RE = re.compile(r"(\d+)(?:\s*[-–]\s*(\d+))?")
_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def _norm(text: str) -> str:
    s = text.translate(_QUOTES).strip().lower()
    s = re.sub(r"^(answer|response|assistant)\s*:\s*", "", s)
    s = s.strip(" \t\r\n\"'`")
    s = re.sub(r"[.!?\"'\s]+$", "", s)
    return re.sub(r"\s+", " ", s)


_REFUSAL_NORM = _norm(REFUSAL_SENTENCE)


def is_refusal_answer(answer: str) -> bool:
    return _norm(answer) == _REFUSAL_NORM


def _bracket_numbers(group: str) -> list[tuple[int, int]]:
    head = group.split("|", 1)[0]  # ignore header metadata after the pipe
    return [(int(a), int(b or a)) for a, b in NUM_RE.findall(head)]


def cited_indices(text: str, n_docs: int) -> list[int]:
    seen: list[int] = []
    for group in BRACKET_RE.findall(text):
        for lo, hi in _bracket_numbers(group):
            if lo < 1 or hi > n_docs or hi < lo:
                logger.warning("Citation %d-%d out of range (1..%d)", lo, hi, n_docs)
            for i in range(max(lo, 1), min(hi, n_docs) + 1):
                if i not in seen:
                    seen.append(i)
    return seen


def renumber_citations(answer: str, n_docs: int) -> tuple[str, list[int]]:

    order = cited_indices(answer, n_docs)
    mapping = {old: new for new, old in enumerate(order, start=1)}

    def repl(m: re.Match) -> str:
        nums: list[int] = []
        for lo, hi in _bracket_numbers(m.group(1)):
            for i in range(max(lo, 1), min(hi, n_docs) + 1):
                if i in mapping and mapping[i] not in nums:
                    nums.append(mapping[i])
        return "[" + ", ".join(map(str, sorted(nums))) + "]" if nums else ""

    return BRACKET_RE.sub(repl, answer), order