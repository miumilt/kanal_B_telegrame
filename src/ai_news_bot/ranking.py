from __future__ import annotations

from ai_news_bot.models import BacklogItem


_KEYWORD_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("release", 4),
    ("launch", 4),
    ("model", 3),
    ("research", 3),
    ("benchmark", 3),
    ("funding", 2),
    ("regulation", 2),
    ("open source", 3),
    ("cli", 2),
)


def score_item(item: BacklogItem) -> int:
    text = f"{item.source_title} {item.summary_candidate}".lower()
    return sum(weight for keyword, weight in _KEYWORD_WEIGHTS if keyword in text)
