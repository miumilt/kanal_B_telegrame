from ai_news_bot.models import BacklogItem
from ai_news_bot.ranking import score_item


def _item(*, title: str, summary: str, source_name: str, priority: int = 6) -> BacklogItem:
    return BacklogItem(
        item_id="item-1",
        source_url="https://example.com/release",
        source_title=title,
        normalized_title=title.lower(),
        topic_fingerprint=title.lower(),
        source_name=source_name,
        published_at="2026-04-25T10:00:00+00:00",
        summary_candidate=summary,
        status="queued",
        first_seen_at="2026-04-25T10:00:00+00:00",
        last_considered_at="2026-04-25T10:00:00+00:00",
        source_tier="tier3_ai_publications",
        source_kind="atom",
        source_priority=priority,
        confirmed=True,
        evidence_urls=["https://example.com/release"],
    )


def test_score_item_penalizes_low_signal_adapter_release_notes():
    adapter_release = _item(
        title="langchain-openai==1.2.1",
        summary="hotfix: bump min core versions (#36996) release(openai): 1.2.1 (#36995)",
        source_name="GitHub Releases - LangChain",
    )
    useful_tool_release = _item(
        title="0.12.3 - Browser Use CLI 2.0",
        summary="The fastest browser automation for AI coding agents. 2x faster and 50% fewer tokens.",
        source_name="GitHub Releases - Browser Use",
    )

    assert score_item(adapter_release) < 20
    assert score_item(adapter_release) < score_item(useful_tool_release)


def test_score_item_boosts_freebie_deals_above_generic_tool_news():
    freebie = _item(
        title="Free AI video editor gives creators 500 credits",
        summary="Public beta includes free credits, a promo code, and a free plan for new users.",
        source_name="Hacker News Free AI",
        priority=5,
    )
    generic_tool = _item(
        title="New AI productivity tool launches",
        summary="The team launched a dashboard for organizing prompts and documents.",
        source_name="Hacker News AI Tool",
        priority=5,
    )

    assert score_item(freebie) >= 25
    assert score_item(freebie) > score_item(generic_tool)
