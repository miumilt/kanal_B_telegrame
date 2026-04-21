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

_TIER_WEIGHTS = {
    "tier1_official": 6,
    "tier2_media": 4,
    "tier3_ai_publications": 3,
    "tier4_community": 1,
}


def score_item(item: BacklogItem) -> int:
    text = f"{item.source_title} {item.summary_candidate}".lower()
    keyword_score = sum(weight for keyword, weight in _KEYWORD_WEIGHTS if keyword in text)
    tier_score = _TIER_WEIGHTS.get(item.source_tier, 0)
    confirmation_score = 3 if item.confirmed else -3
    priority_score = item.source_priority
    evidence_score = max(0, len(item.evidence_urls or []) - 1)
    return keyword_score + tier_score + confirmation_score + priority_score + evidence_score
