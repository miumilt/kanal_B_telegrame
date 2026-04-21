from __future__ import annotations

from collections.abc import Callable

from ai_news_bot.models import BacklogItem


Translator = Callable[[str], str]


def _translate(value: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target="ru").translate(value)
    except Exception:
        return value


def build_digest_text(
    items: list[BacklogItem],
    *,
    translated_title: Translator = _translate,
    translated_body: Translator = _translate,
) -> str:
    parts = ["Daily AI digest for the channel:"]
    for index, item in enumerate(items, start=1):
        parts.append(
            "\n".join(
                [
                    f"{index}. {translated_title(item.source_title)}",
                    translated_body(item.summary_candidate[:280]),
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
    body = translated_body(item.summary_candidate)
    return "\n".join(
        [
            translated_title(item.source_title),
            body[:body_limit],
            f"Source: {item.source_url}",
        ]
    )
