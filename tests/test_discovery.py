from ai_news_bot.discovery import fetch_candidates_from_sources, normalize_title
from ai_news_bot.source_registry import SourceConfig


class FakeEntry(dict):
    pass


def test_normalize_title_collapses_case_and_spacing():
    assert normalize_title("  New  Gemini CLI  ") == "new gemini cli"


def test_fetch_candidates_from_sources_builds_backlog_items(monkeypatch):
    sources = [
        SourceConfig(
            id="openai-blog",
            name="OpenAI Blog",
            tier="tier1_official",
            kind="rss",
            url="https://openai.com/news",
            feed_url="https://openai.com/news/rss.xml",
            language="en",
            priority=10,
            enabled=True,
            tags=("official", "models"),
        )
    ]

    monkeypatch.setattr(
        "ai_news_bot.discovery.parse_feed",
        lambda url: [
            FakeEntry(
                title="Gemini CLI Released",
                link="https://example.com/gemini-cli",
                summary="CLI tool for developers",
                published="2026-04-20T10:00:00+00:00",
                media_thumbnail=[{"url": "/images/feed-thumb.png"}],
                source={"title": "OpenAI Blog"},
            )
        ],
    )
    monkeypatch.setattr(
        "ai_news_bot.discovery.fetch_page_html",
        lambda url: (_ for _ in ()).throw(AssertionError("rss discovery should not fetch full page html")),
    )

    items = fetch_candidates_from_sources(sources, now_iso="2026-04-20T12:00:00+00:00")

    assert len(items) == 1
    assert items[0].source_tier == "tier1_official"
    assert items[0].source_priority == 10
    assert items[0].confirmed is True
    assert items[0].status == "new"
    assert items[0].summary_candidate == "CLI tool for developers"
    assert items[0].category == "major_news"
    assert items[0].image_url == "https://example.com/images/feed-thumb.png"


def test_fetch_candidates_from_sources_marks_community_items_unconfirmed(monkeypatch):
    sources = [
        SourceConfig(
            id="hn-ai",
            name="HN AI",
            tier="tier4_community",
            kind="hackernews",
            url="https://news.ycombinator.com",
            feed_url="https://hnrss.org/newest?q=AI",
            language="en",
            priority=4,
            enabled=True,
            tags=("community", "hn"),
        )
    ]

    monkeypatch.setattr(
        "ai_news_bot.discovery.parse_feed",
        lambda url: [
            FakeEntry(
                title="Interesting AI CLI launch",
                link="https://example.com/hn-thread",
                summary="community discussion",
                published="2026-04-20T10:00:00+00:00",
                source={"title": "HN"},
            )
        ],
    )
    monkeypatch.setattr(
        "ai_news_bot.discovery.fetch_page_html",
        lambda url: (_ for _ in ()).throw(AssertionError("community feed discovery should not fetch full page html")),
    )

    items = fetch_candidates_from_sources(sources, now_iso="2026-04-20T12:00:00+00:00")

    assert len(items) == 1
    assert items[0].status == "observed_unconfirmed"
    assert items[0].confirmed is False
    assert items[0].source_kind == "hackernews"
    assert items[0].category == "major_news"
    assert items[0].image_url is None


def test_fetch_candidates_from_sources_uses_page_text_for_website_sources(monkeypatch):
    sources = [
        SourceConfig(
            id="custom-website",
            name="Custom Website",
            tier="tier2_media",
            kind="website",
            url="https://example.com/news",
            feed_url="https://example.com/feed.xml",
            language="en",
            priority=6,
            enabled=True,
            tags=("media",),
        )
    ]

    monkeypatch.setattr(
        "ai_news_bot.discovery.parse_feed",
        lambda url: [
            FakeEntry(
                title="Website-only summary gap",
                link="https://example.com/full-article",
                summary="",
                published="2026-04-20T10:00:00+00:00",
                media_content=[{"url": "/images/feed-image.png"}],
            )
        ],
    )
    monkeypatch.setattr(
        "ai_news_bot.discovery.fetch_page_html",
        lambda url: (
            "<html><head><meta property='og:image' content='/images/article.png'></head>"
            "<body><img src='https://example.com/images/fallback.png'>Fetched from website body</body></html>"
        ),
    )
    monkeypatch.setattr("ai_news_bot.discovery.extract_text_from_html", lambda html: "Fetched from website body")

    items = fetch_candidates_from_sources(sources, now_iso="2026-04-20T12:00:00+00:00")

    assert len(items) == 1
    assert items[0].summary_candidate == "Fetched from website body"
    assert items[0].category == "major_news"
    assert items[0].image_url == "https://example.com/images/feed-image.png"
