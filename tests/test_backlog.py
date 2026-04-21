from ai_news_bot.backlog import merge_candidates, select_daily_slot_items, select_main_slot_items
from ai_news_bot.models import BacklogItem
from ai_news_bot.ranking import score_item


def test_backlog_item_to_dict_includes_source_metadata_and_empty_evidence_urls():
    item = BacklogItem(
        item_id="item-1",
        source_url="https://example.com/post",
        source_title="Gemini CLI Released",
        normalized_title="gemini cli released",
        topic_fingerprint="gemini-cli-released",
        source_name="OpenAI Blog",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="release details",
        status="observed_unconfirmed",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
        source_tier="tier4_community",
        source_kind="reddit",
        source_priority=4,
        confirmed=False,
        evidence_urls=[],
    )

    data = item.to_dict()

    assert data["source_tier"] == "tier4_community"
    assert data["source_kind"] == "reddit"
    assert data["source_priority"] == 4
    assert data["confirmed"] is False
    assert data["evidence_urls"] == []


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
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=5,
            confirmed=True,
            evidence_urls=["https://example.com/old"],
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
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=5,
            confirmed=True,
            evidence_urls=["https://example.com/gemini-cli"],
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
            source_tier="tier3_ai_publications",
            source_kind="rss",
            source_priority=4,
            confirmed=True,
            evidence_urls=["https://example.com/gemini-cli-dup"],
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
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=5,
            confirmed=True,
            evidence_urls=["https://example.com/feed-item"],
        )
    ]

    merged = merge_candidates(
        [],
        incoming,
        now_iso="2026-04-19T12:00:00+00:00",
        expiry_days=4,
    )

    assert [item.item_id for item in merged] == ["feed-item"]
    assert merged[0].status == "queued"


def test_merge_candidates_confirms_matching_community_topic_with_stronger_source():
    existing = [
        BacklogItem(
            item_id="community",
            source_url="https://example.com/hn-thread",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="HN",
            published_at="2026-04-20T10:00:00+00:00",
            summary_candidate="discussion",
            status="observed_unconfirmed",
            first_seen_at="2026-04-20T10:00:00+00:00",
            last_considered_at="2026-04-20T10:00:00+00:00",
            source_tier="tier4_community",
            source_kind="rss",
            source_priority=4,
            confirmed=False,
            evidence_urls=["https://example.com/hn-thread"],
        )
    ]
    incoming = [
        BacklogItem(
            item_id="official",
            source_url="https://example.com/official-post",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="Google AI",
            published_at="2026-04-20T11:00:00+00:00",
            summary_candidate="official release",
            status="new",
            first_seen_at="2026-04-20T11:00:00+00:00",
            last_considered_at="2026-04-20T11:00:00+00:00",
            source_tier="tier1_official",
            source_kind="rss",
            source_priority=10,
            confirmed=True,
            evidence_urls=["https://example.com/official-post"],
        )
    ]

    merged = merge_candidates(
        existing,
        incoming,
        now_iso="2026-04-20T12:00:00+00:00",
        expiry_days=4,
    )

    assert len(merged) == 1
    assert merged[0].confirmed is True
    assert merged[0].status == "queued"
    assert "https://example.com/hn-thread" in merged[0].evidence_urls
    assert "https://example.com/official-post" in merged[0].evidence_urls


def test_merge_candidates_promotes_confirmed_new_items_to_queued():
    incoming = [
        BacklogItem(
            item_id="official",
            source_url="https://example.com/official-post",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="Google AI",
            published_at="2026-04-20T11:00:00+00:00",
            summary_candidate="official release",
            status="new",
            first_seen_at="2026-04-20T11:00:00+00:00",
            last_considered_at="2026-04-20T11:00:00+00:00",
            source_tier="tier1_official",
            source_kind="rss",
            source_priority=10,
            confirmed=True,
            evidence_urls=["https://example.com/official-post"],
        )
    ]

    merged = merge_candidates(
        [],
        incoming,
        now_iso="2026-04-20T12:00:00+00:00",
        expiry_days=4,
    )

    assert len(merged) == 1
    assert merged[0].status == "queued"


def test_select_main_slot_items_ignores_unconfirmed_community_topics():
    backlog = [
        BacklogItem(
            item_id="community",
            source_url="https://example.com/hn-thread",
            source_title="Unconfirmed launch",
            normalized_title="unconfirmed launch",
            topic_fingerprint="unconfirmed-launch",
            source_name="HN",
            published_at="2026-04-20T10:00:00+00:00",
            summary_candidate="discussion",
            status="observed_unconfirmed",
            first_seen_at="2026-04-20T10:00:00+00:00",
            last_considered_at="2026-04-20T10:00:00+00:00",
            source_tier="tier4_community",
            source_kind="rss",
            source_priority=4,
            confirmed=False,
            evidence_urls=["https://example.com/hn-thread"],
        )
    ]

    assert select_main_slot_items(backlog) == []


def test_score_item_prefers_confirmed_high_priority_sources_with_evidence():
    official = BacklogItem(
        item_id="official",
        source_url="https://example.com/official",
        source_title="Gemini CLI Release",
        normalized_title="gemini cli release",
        topic_fingerprint="gemini-cli-release",
        source_name="Google AI",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="major CLI release benchmark",
        status="queued",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
        source_tier="tier1_official",
        source_kind="rss",
        source_priority=10,
        confirmed=True,
        evidence_urls=["https://example.com/official", "https://example.com/reuters"],
    )
    community = BacklogItem(
        item_id="community",
        source_url="https://example.com/community",
        source_title="Gemini CLI release rumor",
        normalized_title="gemini cli release rumor",
        topic_fingerprint="gemini-cli-release-rumor",
        source_name="HN",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="discussion",
        status="observed_unconfirmed",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
        source_tier="tier4_community",
        source_kind="rss",
        source_priority=4,
        confirmed=False,
        evidence_urls=["https://example.com/community"],
    )

    assert score_item(official) > score_item(community)


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
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=5,
            confirmed=True,
            evidence_urls=["https://example.com/medium"],
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
            source_tier="tier1_official",
            source_kind="rss",
            source_priority=10,
            confirmed=True,
            evidence_urls=["https://example.com/high"],
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
            source_tier="tier3_ai_publications",
            source_kind="rss",
            source_priority=3,
            confirmed=True,
            evidence_urls=["https://example.com/low"],
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
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=5,
            confirmed=True,
            evidence_urls=["https://example.com/ignored"],
        ),
    ]

    selected = select_main_slot_items(backlog, limit=2)

    assert [item.item_id for item in selected] == ["high", "medium"]


def test_select_daily_slot_items_prefers_category_variety_when_available():
    backlog = [
        BacklogItem(
            item_id="major-1",
            source_url="https://example.com/major-1",
            source_title="Major News One",
            normalized_title="major news one",
            topic_fingerprint="major-news-one",
            source_name="Example",
            published_at="2026-04-19T10:00:00+00:00",
            summary_candidate="major news item one",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
            source_tier="tier1_official",
            source_kind="rss",
            source_priority=10,
            confirmed=True,
            evidence_urls=["https://example.com/major-1"],
            category="major_news",
        ),
        BacklogItem(
            item_id="major-2",
            source_url="https://example.com/major-2",
            source_title="Major News Two",
            normalized_title="major news two",
            topic_fingerprint="major-news-two",
            source_name="Example",
            published_at="2026-04-19T11:00:00+00:00",
            summary_candidate="major news item two",
            status="queued",
            first_seen_at="2026-04-19T11:00:00+00:00",
            last_considered_at="2026-04-19T11:00:00+00:00",
            source_tier="tier1_official",
            source_kind="rss",
            source_priority=9,
            confirmed=True,
            evidence_urls=["https://example.com/major-2"],
            category="major_news",
        ),
        BacklogItem(
            item_id="freebie-1",
            source_url="https://example.com/freebie-1",
            source_title="Free Tool",
            normalized_title="free tool",
            topic_fingerprint="free-tool",
            source_name="Example",
            published_at="2026-04-19T12:00:00+00:00",
            summary_candidate="freebie item",
            status="queued",
            first_seen_at="2026-04-19T12:00:00+00:00",
            last_considered_at="2026-04-19T12:00:00+00:00",
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=7,
            confirmed=True,
            evidence_urls=["https://example.com/freebie-1"],
            category="freebie/useful_find",
        ),
        BacklogItem(
            item_id="useful-1",
            source_url="https://example.com/useful-1",
            source_title="Useful Find",
            normalized_title="useful find",
            topic_fingerprint="useful-find",
            source_name="Example",
            published_at="2026-04-19T13:00:00+00:00",
            summary_candidate="useful find item",
            status="queued",
            first_seen_at="2026-04-19T13:00:00+00:00",
            last_considered_at="2026-04-19T13:00:00+00:00",
            source_tier="tier2_media",
            source_kind="rss",
            source_priority=6,
            confirmed=True,
            evidence_urls=["https://example.com/useful-1"],
            category="major_news",
        ),
    ]

    selected = select_daily_slot_items(backlog)

    assert [item.item_id for item in selected] == ["major-1", "freebie-1", "major-2"]
    assert [item.category for item in selected] == ["major_news", "freebie/useful_find", "major_news"]
