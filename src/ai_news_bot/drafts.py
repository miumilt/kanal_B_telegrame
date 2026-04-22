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


def _clean_text(value: str) -> str:
    without_tags = HTML_TAG_PATTERN.sub(" ", value)
    unescaped = html.unescape(without_tags)
    normalized = WHITESPACE_PATTERN.sub(" ", unescaped).strip()
    return normalized


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
    clean_summary = _clean_text(item.summary_candidate)
    body = _clean_text(translated_body(clean_summary))
    return "\n".join(
        [
            _clean_text(translated_title(item.source_title)),
            body[:body_limit],
            f"Source: {item.source_url}",
        ]
    )
