from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}

COMPANY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("openai", ("openai", "chatgpt")),
    ("anthropic", ("anthropic", "claude")),
    ("google", ("google", "deepmind", "gemini")),
    ("meta", ("meta ai", "llama")),
    ("xai", ("xai", "grok")),
    ("mistral", ("mistral", "mixtral", "magistral")),
    ("deepseek", ("deepseek",)),
    ("nvidia", ("nvidia",)),
    ("huggingface", ("hugging face", "huggingface")),
    ("microsoft", ("microsoft", "copilot")),
    ("bytedance", ("bytedance", "capcut", "tiktok", "dreamina")),
)

ACTION_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("release", ("release", "released", "launch", "launched", "introducing", "rollout", "rolling out", "available")),
    ("free", ("free", "free access", "free tier", "no waitlist")),
    ("benchmark", ("benchmark", "beats", "leaderboard", "eval", "evaluation")),
    ("open-source", ("open source", "open-source", "open weights")),
)

MODEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bgpt[-\s]?\d+(?:\.\d+)?(?:[-\s]?(?:pro|mini|nano|codex|thinking))?\b"),
    re.compile(r"\bchatgpt[-\s]?\d+(?:\.\d+)?\b"),
    re.compile(r"\bclaude[-\s]?\d+(?:\.\d+)?\b|\bopus[-\s]?\d*(?:\.\d+)?\b|\bsonnet[-\s]?\d*(?:\.\d+)?\b"),
    re.compile(r"\bgemini[-\s]?\d+(?:\.\d+)?(?:[-\s]?(?:pro|flash))?\b"),
    re.compile(r"\bllama[-\s]?\d+(?:\.\d+)?\b"),
    re.compile(r"\bgrok[-\s]?\d+(?:\.\d+)?\b"),
    re.compile(r"\bdeepseek[-\s]?[a-z]?\d+(?:\.\d+)?(?:[-\s]?(?:pro|flash|max))?\b"),
    re.compile(r"\bqwen[-\s]?\d+(?:\.\d+)?\b"),
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "new",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def normalize_topic_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.+-]+", " ", value.lower())).strip()


def _find_aliases(text: str, aliases: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    found = []
    for canonical, variants in aliases:
        if any(variant in text for variant in variants):
            found.append(canonical)
    return found


def _find_models(text: str) -> list[str]:
    models: list[str] = []
    for pattern in MODEL_PATTERNS:
        for match in pattern.findall(text):
            model = normalize_topic_text(match if isinstance(match, str) else match[0])
            if model.startswith("chatgpt"):
                model = model.replace("chatgpt", "gpt", 1)
            if model and model not in models:
                models.append(model.replace(" ", "-"))
    return models


def _fallback_title_key(title: str) -> str:
    words = [word for word in normalize_topic_text(title).split() if word not in STOPWORDS]
    return "-".join(words[:8])


def build_topic_fingerprint(title: str, summary: str = "") -> str:
    text = normalize_topic_text(f"{title} {summary}")
    companies = _find_aliases(text, COMPANY_ALIASES)
    models = _find_models(text)
    actions = _find_aliases(text, ACTION_ALIASES)

    if companies or models:
        parts = ["topic"]
        parts.extend(companies[:2] or ["unknown"])
        parts.extend(models[:2])
        parts.extend(actions[:1] or ["update"])
        return ":".join(parts)

    return f"title:{_fallback_title_key(title)}"
