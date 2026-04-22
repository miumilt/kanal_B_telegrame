from __future__ import annotations

import re

from ai_news_bot.models import BacklogItem


FREEBIE_PHRASES = (
    "free access",
    "free for everyone",
    "free tier",
    "free trial",
    "free plan",
    "free credits",
    "open-source",
    "open source",
    "open weights",
    "no waitlist",
)

CATEGORY_LABELS = {
    "major_news": "Major news",
    "freebie/useful_find": "Useful find",
}


def classify_candidate(item: BacklogItem) -> str:
    haystack = f"{item.source_title} {item.summary_candidate}".lower()
    if any(pattern.search(haystack) for pattern in FREEBIE_PATTERNS):
        return "freebie/useful_find"
    return "major_news"


def build_header_label(index: int, total: int, category: str) -> str:
    return f"Draft {index}/{total} - {_category_label(category)}"


def _phrase_pattern(phrase: str) -> str:
    parts = [re.escape(part) for part in phrase.split()]
    return r"[\s-]+".join(parts)


def _category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").replace("/", " ").title())


FREEBIE_PATTERNS = tuple(
    re.compile(rf"(?<!\w){_phrase_pattern(phrase)}(?!\w)")
    for phrase in FREEBIE_PHRASES
)
