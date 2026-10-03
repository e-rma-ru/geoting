from __future__ import annotations

import difflib
import re
from typing import List, Optional

CONTEXT_KEYWORDS = (
    "center", "centre", "центр", "школ", "языков", "английск", "англ",
    "english", "language", "school", "курс", "академи", "academy",
    "study", "обучен", "занят", "класс", "классы", "репетитор",
)

SINGLE_WORD_FUZZY_THRESHOLD = 0.86
MULTI_WORD_FUZZY_THRESHOLD = 0.84


def normalize_text(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def find_brand_mentions(text: str, aliases: List[str]) -> List[int]:
    """Returns sorted word-indices where the brand is mentioned.

    Heuristic rules:
    - Multi-word aliases ("Priority Center") match exactly or with fuzzy
      similarity over sliding word windows.
    - Single-word aliases ("Priority", "Приоритет") only count when a
      brand/education context keyword appears within a small window, so a
      standalone ambiguous word does not count as a mention.
    """
    if not aliases:
        return []
    norm = normalize_text(text)
    words = norm.split()
    if not words:
        return []

    multi = [a for a in aliases if len(normalize_text(a).split()) >= 2]
    single = [a for a in aliases if len(normalize_text(a).split()) == 1]

    positions: set[int] = set()

    for alias in multi:
        aw = normalize_text(alias).split()
        n = len(aw)
        if n > len(words):
            continue
        for i in range(len(words) - n + 1):
            window = " ".join(words[i : i + n])
            if _ratio(window, " ".join(aw)) >= MULTI_WORD_FUZZY_THRESHOLD:
                positions.update(range(i, i + n))

    if positions:
        return sorted(positions)

    for alias in single:
        aw = normalize_text(alias).split()
        if len(aw) != 1:
            continue
        for i, w in enumerate(words):
            if w != aw[0]:
                continue
            lo = max(0, i - 2)
            hi = min(len(words), i + 3)
            context = " ".join(words[lo:hi])
            if any(k in context for k in CONTEXT_KEYWORDS):
                positions.add(i)

    return sorted(positions)


def detect_brand_mention(text: str, aliases: List[str]) -> tuple[bool, List[int]]:
    positions = find_brand_mentions(text, aliases)
    return bool(positions), positions


def brand_mentioned_in_string(text: str, aliases: List[str]) -> bool:
    return detect_brand_mention(text, aliases)[0]


def mentions_any_alias(text: str, aliases: List[str]) -> bool:
    """Loose check used for citation classification (aliases + name)."""
    lowered = normalize_text(text)
    for alias in aliases:
        a = normalize_text(alias)
        if a and a in lowered:
            return True
    return False
