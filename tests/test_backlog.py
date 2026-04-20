from ai_news_bot.backlog import merge_candidates, select_main_slot_items
from ai_news_bot.models import BacklogItem


def test_merge_candidates_drops_duplicate_normalized_titles_and_expires_old_items():
    existing = [
        BacklogItem(
            item_id="old",
            source_url="https://example.com/old",
            source_title="Old Story",
            normalized_title="old story",
            topic_fingerprint="old-story",
            source_name="Example",
            published_at="2026-04-10T10:00:00+00:00",
            summary_candidate="old",
            status="queued",
            first_seen_at="2026-04-10T10:00:00+00:00",
            last_considered_at="2026-04-10T10:00:00+00:00",
        )
    ]
    incoming = [
        BacklogItem(
            item_id="new",
            source_url="https://example.com/gemini-cli",
            source_title="New Gemini CLI",
            normalized_title="new gemini cli",
            topic_fingerprint="new-gemini-cli",
            source_name="Example",
            published_at="2026-04-19T10:00:00+00:00",
            summary_candidate="new",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
        ),
        BacklogItem(
            item_id="dup",
            source_url="https://example.com/gemini-cli-dup",
            source_title="New   Gemini CLI",
            normalized_title="new gemini cli",
            topic_fingerprint="new-gemini-cli",
            source_name="Another",
            published_at="2026-04-19T11:00:00+00:00",
            summary_candidate="dup",
            status="queued",
            first_seen_at="2026-04-19T11:00:00+00:00",
            last_considered_at="2026-04-19T11:00:00+00:00",
        ),
    ]

    merged = merge_candidates(
        existing,
        incoming,
        now_iso="2026-04-19T12:00:00+00:00",
        expiry_days=4,
    )

    assert [item.item_id for item in merged] == ["new"]


def test_merge_candidates_accepts_rss_style_published_at():
    incoming = [
        BacklogItem(
            item_id="feed-item",
            source_url="https://example.com/feed-item",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="Example",
            published_at="Sat, 19 Apr 2026 10:00:00 GMT",
            summary_candidate="release",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
        )
    ]

    merged = merge_candidates(
        [],
        incoming,
        now_iso="2026-04-19T12:00:00+00:00",
        expiry_days=4,
    )

    assert [item.item_id for item in merged] == ["feed-item"]


def test_select_main_slot_items_returns_highest_scoring_queued_items():
    backlog = [
        BacklogItem(
            item_id="medium",
            source_url="https://example.com/medium",
            source_title="AI Model Update",
            normalized_title="ai model update",
            topic_fingerprint="ai-model-update",
            source_name="Example",
            published_at="2026-04-19T10:00:00+00:00",
            summary_candidate="model update",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
        ),
        BacklogItem(
            item_id="high",
            source_url="https://example.com/high",
            source_title="AI Model Release Launch",
            normalized_title="ai model release launch",
            topic_fingerprint="ai-model-release-launch",
            source_name="Example",
            published_at="2026-04-19T11:00:00+00:00",
            summary_candidate="release launch",
            status="queued",
            first_seen_at="2026-04-19T11:00:00+00:00",
            last_considered_at="2026-04-19T11:00:00+00:00",
        ),
        BacklogItem(
            item_id="low",
            source_url="https://example.com/low",
            source_title="AI News",
            normalized_title="ai news",
            topic_fingerprint="ai-news",
            source_name="Example",
            published_at="2026-04-19T12:00:00+00:00",
            summary_candidate="news",
            status="queued",
            first_seen_at="2026-04-19T12:00:00+00:00",
            last_considered_at="2026-04-19T12:00:00+00:00",
        ),
        BacklogItem(
            item_id="ignored",
            source_url="https://example.com/ignored",
            source_title="AI Model Release",
            normalized_title="ai model release",
            topic_fingerprint="ai-model-release",
            source_name="Example",
            published_at="2026-04-19T13:00:00+00:00",
            summary_candidate="release",
            status="published",
            first_seen_at="2026-04-19T13:00:00+00:00",
            last_considered_at="2026-04-19T13:00:00+00:00",
        ),
    ]

    selected = select_main_slot_items(backlog, limit=2)

    assert [item.item_id for item in selected] == ["high", "medium"]
