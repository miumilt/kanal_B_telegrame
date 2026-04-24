from __future__ import annotations

from collections.abc import Callable
import html
import re

from ai_news_bot.models import BacklogItem


Translator = Callable[[str], str]


def _translate(value: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target="ru").translate(value)
    except Exception:
        return value


HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|[\n•]+")
CLAUSE_SPLIT_PATTERN = re.compile(r";\s+|,\s+")


def _clean_text(value: str) -> str:
    without_tags = HTML_TAG_PATTERN.sub(" ", value)
    unescaped = html.unescape(without_tags)
    normalized = WHITESPACE_PATTERN.sub(" ", unescaped).strip()
    return normalized


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    cropped = value[: limit - 1].rstrip()
    boundary = max(cropped.rfind("."), cropped.rfind("!"), cropped.rfind("?"), cropped.rfind(";"), cropped.rfind(","))
    if boundary >= limit // 2:
        cropped = cropped[:boundary]
    else:
        space = cropped.rfind(" ")
        if space >= limit // 2:
            cropped = cropped[:space]
    return f"{cropped.rstrip()}..."


def _strip_final_punctuation(value: str) -> str:
    return value.rstrip(" .!?;:")


def _ensure_sentence(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if value[-1] in ".!?":
        return value
    return f"{value}."


def _extract_points(value: str, *, max_points: int) -> list[str]:
    sentences = [_clean_text(part) for part in SENTENCE_SPLIT_PATTERN.split(value)]
    points = [part for part in sentences if part]

    if len(points) <= 1 and points:
        clauses = [_clean_text(part) for part in CLAUSE_SPLIT_PATTERN.split(points[0])]
        if len([part for part in clauses if part]) >= 3:
            points = [part for part in clauses if part]

    return points[:max_points]


def _link_label(category: str) -> str:
    if category == "freebie/useful_find":
        return "Тестим здесь:"
    return "Подробнее:"


def build_digest_text(
    items: list[BacklogItem],
    *,
    translated_title: Translator = _translate,
    translated_body: Translator = _translate,
) -> str:
    parts = ["Daily AI digest for the channel:"]
    for index, item in enumerate(items, start=1):
        clean_title = _clean_text(translated_title(item.source_title))
        clean_body = _clean_text(translated_body(_clean_text(item.summary_candidate)))
        parts.append(
            "\n".join(
                [
                    f"{index}. {clean_title}",
                    clean_body[:280],
                    f"Source: {item.source_url}",
                ]
            )
        )
    return "\n\n".join(parts)


def build_short_post_text(
    item: BacklogItem,
    *,
    translated_title: Translator = _translate,
    translated_body: Translator = _translate,
) -> str:
    return _build_post_text(
        item,
        body_limit=280,
        translated_title=translated_title,
        translated_body=translated_body,
    )


def build_single_post_text(
    item: BacklogItem,
    *,
    translated_title: Translator = _translate,
    translated_body: Translator = _translate,
) -> str:
    return _build_post_text(
        item,
        body_limit=240,
        translated_title=translated_title,
        translated_body=translated_body,
    )


def _build_post_text(
    item: BacklogItem,
    *,
    body_limit: int,
    translated_title: Translator,
    translated_body: Translator,
) -> str:
    title = _truncate(_clean_text(translated_title(item.source_title)), 150)
    clean_summary = _clean_text(item.summary_candidate)
    body = _clean_text(translated_body(clean_summary))
    points = _extract_points(body, max_points=5)

    if points:
        lead = _truncate(_strip_final_punctuation(points[0]), body_limit)
        intro = _ensure_sentence(f"{title} — {lead}")
    else:
        intro = _ensure_sentence(title)

    lines = [intro]
    bullets = [_truncate(_strip_final_punctuation(point), 120) for point in points[1:5]]
    if bullets:
        lines.extend(["", "Главное:"])
        lines.extend(f"• {_ensure_sentence(point)}" for point in bullets)

    lines.extend(["", f"{_link_label(item.category)} {item.source_url}"])
    return "\n".join(lines)
