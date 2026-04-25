from __future__ import annotations

import re

from ai_news_bot.models import BacklogItem


_KEYWORD_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("introducing", 3),
    ("announcing", 3),
    ("release", 4),
    ("released", 4),
    ("launch", 4),
    ("launched", 4),
    ("ships", 4),
    ("rolling out", 3),
    ("model", 3),
    ("research", 3),
    ("benchmark", 3),
    ("leaderboard", 3),
    ("funding", 2),
    ("regulation", 2),
    ("open source", 3),
    ("open weights", 4),
    ("cli", 2),
    ("agent", 3),
    ("agents", 3),
    ("api", 2),
    ("demo", 3),
    ("free", 1),
    ("try", 2),
    ("tool", 1),
    ("github", 2),
    ("show hn", 3),
)

_FRONTIER_SOURCE_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("openai", 18),
    ("anthropic", 16),
    ("google deepmind", 16),
    ("google ai", 14),
    ("deepmind", 14),
    ("meta ai", 13),
    ("xai", 13),
    ("mistral", 12),
    ("microsoft", 10),
    ("nvidia", 9),
    ("hugging face", 8),
    ("the decoder", 8),
    ("tldr ai", 7),
    ("product hunt", 7),
    ("simon willison", 7),
    ("karpathy", 7),
    ("one useful thing", 7),
    ("ethan mollick", 7),
    ("import ai", 7),
    ("interconnects", 7),
    ("chip huyen", 6),
    ("latent space", 6),
    ("github releases", 6),
)

_FRONTIER_MODEL_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bgpt[-\s]?\d+(?:\.\d+)?(?:[-\s]?(?:pro|mini|nano|codex|thinking))?\b"), 22),
    (re.compile(r"\bchatgpt\b"), 12),
    (re.compile(r"\bclaude\b|\bopus\b|\bsonnet\b|\bhaiku\b"), 18),
    (re.compile(r"\bgemini\b"), 18),
    (re.compile(r"\bllama[-\s]?\d+(?:\.\d+)?\b"), 16),
    (re.compile(r"\bgrok[-\s]?\d+(?:\.\d+)?\b"), 16),
    (re.compile(r"\bmistral\b|\bmixtral\b|\bmagistral\b"), 14),
    (re.compile(r"\bcodex\b"), 12),
    (re.compile(r"\bagents?\s+sdk\b|\bworkspace agents?\b"), 9),
    (re.compile(r"\bproduct\s+hunt\b|\bshow\s+hn\b"), 8),
    (re.compile(r"\bfree\s+(?:tier|trial|access|credits|plan|to\s+use)\b"), 8),
    (re.compile(r"\bopen[-\s]?weights?\b|\bopen[-\s]?source\b"), 8),
)

_SECONDARY_SOURCE_PENALTIES: tuple[tuple[str, int], ...] = (
    ("xiaomi", -5),
    ("alibaba", -4),
    ("qwen", -4),
    ("baidu", -4),
    ("austria", -6),
)

_TIER_WEIGHTS = {
    "tier1_official": 6,
    "tier2_media": 4,
    "tier3_ai_publications": 3,
    "tier4_community": 1,
}


def _frontier_source_score(item: BacklogItem) -> int:
    haystack = f"{item.source_name} {item.source_title}".lower()
    return sum(weight for name, weight in _FRONTIER_SOURCE_WEIGHTS if name in haystack)


def _frontier_model_score(text: str) -> int:
    return sum(weight for pattern, weight in _FRONTIER_MODEL_PATTERNS if pattern.search(text))


def _secondary_penalty(text: str) -> int:
    return sum(weight for keyword, weight in _SECONDARY_SOURCE_PENALTIES if keyword in text)


def score_item(item: BacklogItem) -> int:
    text = f"{item.source_title} {item.summary_candidate}".lower()
    keyword_score = sum(weight for keyword, weight in _KEYWORD_WEIGHTS if keyword in text)
    tier_score = _TIER_WEIGHTS.get(item.source_tier, 0)
    confirmation_score = 3 if item.confirmed else -3
    priority_score = item.source_priority
    evidence_score = max(0, len(item.evidence_urls or []) - 1) * 4
    frontier_score = _frontier_source_score(item) + _frontier_model_score(text)
    return (
        keyword_score
        + tier_score
        + confirmation_score
        + priority_score
        + evidence_score
        + frontier_score
        + _secondary_penalty(text)
    )
