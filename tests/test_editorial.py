from ai_news_bot.editorial import build_header_label, classify_candidate, is_ai_relevant_candidate
from ai_news_bot.models import BacklogItem


def make_item(*, title: str, summary: str) -> BacklogItem:
    return BacklogItem(
        item_id="item-1",
        source_url="https://example.com/story",
        source_title=title,
        normalized_title=title.lower(),
        topic_fingerprint="story",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate=summary,
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )


def test_classify_candidate_marks_freebie_keywords_as_useful_find():
    item = make_item(
        title="ByteDance rolls out Dreamina free for everyone",
        summary="Public rollout, free access, try it now.",
    )

    assert classify_candidate(item) == "freebie/useful_find"


def test_classify_candidate_defaults_to_major_news():
    item = make_item(
        title="Claude now builds map routes",
        summary="Plans the route, suggests places, and accounts for schedules.",
    )

    assert classify_candidate(item) == "major_news"


def test_classify_candidate_ignores_free_substrings_without_intent():
    item = make_item(
        title="Claude is freeing up routing logic",
        summary="The team is free-forming the plan while keeping the rollout focused.",
    )

    assert classify_candidate(item) == "major_news"


def test_classify_candidate_ignores_generic_launch_copy():
    item = make_item(
        title="New model public rollout available now",
        summary="Try it now for teams who want to test the release.",
    )

    assert classify_candidate(item) == "major_news"


def test_is_ai_relevant_candidate_detects_ai_tooling_signal():
    item = make_item(
        title="Show HN: an AI agent that books meetings",
        summary="The demo uses an LLM to call tools and plan tasks.",
    )

    assert is_ai_relevant_candidate(item) is True


def test_is_ai_relevant_candidate_rejects_unrelated_product_launch():
    item = make_item(
        title="A new calendar app for families",
        summary="Shared lists, reminders, and simple scheduling.",
    )

    assert is_ai_relevant_candidate(item) is False


def test_build_header_label_formats_candidate_position_and_category():
    assert build_header_label(1, 3, "major_news") == "Draft 1/3 - Major news"
    assert build_header_label(2, 3, "freebie/useful_find") == "Draft 2/3 - Useful find"
