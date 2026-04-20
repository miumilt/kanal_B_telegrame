import sys
import types

from ai_news_bot.drafts import build_digest_text, build_short_post_text
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
        "RU:Gemini CLI Released\n"
        "RU:CLI tool for developers.\n"
        "Source: https://example.com/1"
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

    assert text.splitlines()[1] == "x" * 280
    assert len(text.splitlines()[1]) == 280
