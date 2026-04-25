import sys
import types

from ai_news_bot.drafts import build_digest_text, build_short_post_text, build_single_post_text
from ai_news_bot.models import BacklogItem


def test_build_digest_text_renders_multiple_items():
    items = [
        BacklogItem(
            item_id="1",
            source_url="https://example.com/1",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="Example",
            published_at="2026-04-19T10:00:00+00:00",
            summary_candidate="CLI tool for developers.",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
        ),
        BacklogItem(
            item_id="2",
            source_url="https://example.com/2",
            source_title="Open Model Released",
            normalized_title="open model released",
            topic_fingerprint="open-model-released",
            source_name="Example",
            published_at="2026-04-19T11:00:00+00:00",
            summary_candidate="Open weights and benchmarks.",
            status="queued",
            first_seen_at="2026-04-19T11:00:00+00:00",
            last_considered_at="2026-04-19T11:00:00+00:00",
        )
    ]

    text = build_digest_text(
        items,
        translated_title=lambda s: f"RU:{s}",
        translated_body=lambda s: f"RU:{s}",
    )

    assert text == (
        "Daily AI digest for the channel:\n\n"
        "1. RU:Gemini CLI Released\n"
        "RU:CLI tool for developers.\n"
        "Source: https://example.com/1\n\n"
        "2. RU:Open Model Released\n"
        "RU:Open weights and benchmarks.\n"
        "Source: https://example.com/2"
    )


def test_build_short_post_text_renders_single_item():
    item = BacklogItem(
        item_id="1",
        source_url="https://example.com/1",
        source_title="Gemini CLI Released",
        normalized_title="gemini cli released",
        topic_fingerprint="gemini-cli-released",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="CLI tool for developers.",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_short_post_text(
        item,
        translated_title=lambda s: f"RU:{s}",
        translated_body=lambda s: f"RU:{s}",
    )

    assert text == (
        "RU:Gemini CLI Released — RU:CLI tool for developers.\n\n"
        "Где посмотреть: https://example.com/1\n"
        "Источник: Example"
    )


def test_translate_falls_back_when_translator_raises(monkeypatch):
    class BrokenTranslator:
        def __init__(self, *args, **kwargs):
            pass

        def translate(self, value):
            raise RuntimeError("translator down")

    monkeypatch.setitem(
        sys.modules,
        "deep_translator",
        types.SimpleNamespace(GoogleTranslator=BrokenTranslator),
    )

    from ai_news_bot import drafts

    assert drafts._translate("Keep original text") == "Keep original text"


def test_build_short_post_text_truncates_long_summaries_to_280_characters():
    item = BacklogItem(
        item_id="long",
        source_url="https://example.com/long",
        source_title="Long Summary Story",
        normalized_title="long summary story",
        topic_fingerprint="long-summary-story",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="x" * 281,
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_short_post_text(
        item,
        translated_title=lambda s: s,
        translated_body=lambda s: s,
    )

    assert text.splitlines()[0].startswith("Long Summary Story — ")
    assert len(text.splitlines()[0]) <= 305
    assert text.splitlines()[-2] == "Где посмотреть: https://example.com/long"
    assert text.splitlines()[-1] == "Источник: Example"


def test_build_short_post_text_truncates_after_translation_expands_text():
    item = BacklogItem(
        item_id="expand-short",
        source_url="https://example.com/expand-short",
        source_title="Short expansion",
        normalized_title="short expansion",
        topic_fingerprint="short-expansion",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="x" * 200,
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_short_post_text(
        item,
        translated_title=lambda s: s,
        translated_body=lambda s: s.upper() * 2,
    )

    assert text.splitlines()[0].startswith("Short expansion — ")
    assert "X" * 100 in text.splitlines()[0]
    assert text.splitlines()[-2] == "Где посмотреть: https://example.com/expand-short"
    assert text.splitlines()[-1] == "Источник: Example"


def test_build_single_post_text_renders_short_telegram_style_output():
    item = BacklogItem(
        item_id="1",
        source_url="https://example.com/1",
        source_title="Claude now builds map routes",
        normalized_title="claude now builds map routes",
        topic_fingerprint="claude-map-routes",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="Plans the route, suggests places, and accounts for schedules.",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_single_post_text(
        item,
        translated_title=lambda s: f"RU:{s}",
        translated_body=lambda s: f"RU:{s}",
    )

    assert text == (
        "RU:Claude now builds map routes — RU:Plans the route.\n"
        "suggests places. and accounts for schedules.\n\n"
        "Где посмотреть: https://example.com/1\n"
        "Источник: Example"
    )


def test_build_single_post_text_truncates_long_summaries_to_240_characters():
    item = BacklogItem(
        item_id="long",
        source_url="https://example.com/long",
        source_title="Long Summary Story",
        normalized_title="long summary story",
        topic_fingerprint="long-summary-story",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="x" * 241,
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_single_post_text(
        item,
        translated_title=lambda s: s,
        translated_body=lambda s: s,
    )

    assert text.splitlines()[0].startswith("Long Summary Story — ")
    assert len(text.splitlines()[0]) <= 265
    assert text.splitlines()[-2] == "Где посмотреть: https://example.com/long"
    assert text.splitlines()[-1] == "Источник: Example"


def test_build_single_post_text_truncates_after_translation_expands_text():
    item = BacklogItem(
        item_id="expand-single",
        source_url="https://example.com/expand-single",
        source_title="Single expansion",
        normalized_title="single expansion",
        topic_fingerprint="single-expansion",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="x" * 200,
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_single_post_text(
        item,
        translated_title=lambda s: s,
        translated_body=lambda s: s.upper() * 2,
    )

    assert text.splitlines()[0].startswith("Single expansion — ")
    assert "X" * 100 in text.splitlines()[0]
    assert text.splitlines()[-2] == "Где посмотреть: https://example.com/expand-single"
    assert text.splitlines()[-1] == "Источник: Example"


def test_build_single_post_text_strips_html_and_normalizes_whitespace():
    item = BacklogItem(
        item_id="html",
        source_url="https://example.com/html",
        source_title="OpenAI <b>Privacy</b> Filter",
        normalized_title="openai privacy filter",
        topic_fingerprint="openai-privacy-filter",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="<p>Detects <b>PII</b> in text</p>\n<p>and cleans it.</p>",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_single_post_text(
        item,
        translated_title=lambda s: s,
        translated_body=lambda s: s,
    )

    assert text == (
        "OpenAI Privacy Filter — Detects PII in text and cleans it.\n\n"
        "Где посмотреть: https://example.com/html\n"
        "Источник: Example"
    )


def test_build_single_post_text_uses_freebie_link_label():
    item = BacklogItem(
        item_id="freebie",
        source_url="https://example.com/freebie",
        source_title="Dreamina is free for everyone",
        normalized_title="dreamina is free for everyone",
        topic_fingerprint="dreamina-free",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="Image generation, video generation, and prompt cleanup in one service.",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
        category="freebie/useful_find",
    )

    text = build_single_post_text(
        item,
        translated_title=lambda s: s,
        translated_body=lambda s: s,
    )

    assert text.endswith("Тестим здесь: https://example.com/freebie\nИсточник: Example")
