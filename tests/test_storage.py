import json
from pathlib import Path

from ai_news_bot.models import BacklogItem, DraftRecord
from ai_news_bot.storage import JsonStateStore


def test_store_round_trip_backlog_and_draft(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    item = BacklogItem(
        item_id="item-1",
        source_url="https://example.com/story",
        source_title="Open Model Release",
        normalized_title="open model release",
        topic_fingerprint="open-model-release",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="Model released.",
        status="queued",
        first_seen_at="2026-04-19T11:00:00+00:00",
        last_considered_at="2026-04-19T11:00:00+00:00",
        source_tier="tier1_official",
        source_kind="rss",
        source_priority=10,
        confirmed=True,
        evidence_urls=["https://example.com/story"],
        category="major_news",
        image_url="https://example.com/story.jpg",
    )
    draft = DraftRecord(
        draft_id="draft-1",
        generated_text="text",
        current_text="text",
        selected_story_ids=["item-1"],
        draft_type="digest",
        status="pending",
        created_at="2026-04-19T14:30:00+00:00",
        category="news",
        header_label="Top story",
        image_url=None,
    )

    store.save_backlog([item])
    store.save_current_draft(draft)
    store.save_owner_drafts([draft])

    assert store.load_backlog()[0].item_id == "item-1"
    assert store.load_backlog()[0].category == "major_news"
    assert store.load_backlog()[0].image_url == "https://example.com/story.jpg"
    loaded = store.load_current_draft()
    assert loaded.draft_id == "draft-1"
    assert loaded.category == "news"
    assert loaded.header_label == "Top story"
    assert loaded.image_url is None
    assert store.load_owner_drafts()[0].draft_id == "draft-1"


def test_store_round_trip_backlog_includes_metadata(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    item = BacklogItem(
        item_id="item-2",
        source_url="https://example.com/meta",
        source_title="Open Model Meta",
        normalized_title="open model meta",
        topic_fingerprint="open-model-meta",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="Meta story.",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
        source_tier="tier3_ai_publications",
        source_kind="atom",
        source_priority=3,
        confirmed=False,
        evidence_urls=[],
        category="freebie/useful_find",
        image_url="https://example.com/meta.png",
    )

    store.save_backlog([item])
    loaded = store.load_backlog()[0]

    assert loaded.source_tier == "tier3_ai_publications"
    assert loaded.source_kind == "atom"
    assert loaded.source_priority == 3
    assert loaded.confirmed is False
    assert loaded.evidence_urls == []
    assert loaded.category == "freebie/useful_find"
    assert loaded.image_url == "https://example.com/meta.png"


def test_store_loads_old_backlog_records_with_safe_defaults(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    (tmp_path / "backlog.json").write_text(
        json.dumps(
            [
                {
                    "item_id": "legacy-item",
                    "source_url": "https://example.com/legacy",
                    "source_title": "Legacy Story",
                    "normalized_title": "legacy story",
                    "topic_fingerprint": "legacy-story",
                    "source_name": "Example",
                    "published_at": "2026-04-19T10:00:00+00:00",
                    "summary_candidate": "Legacy story.",
                    "status": "queued",
                    "first_seen_at": "2026-04-19T10:00:00+00:00",
                    "last_considered_at": "2026-04-19T10:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )

    loaded = store.load_backlog()[0]

    assert loaded.item_id == "legacy-item"
    assert loaded.source_tier == "tier2_media"
    assert loaded.source_kind == "rss"
    assert loaded.source_priority == 0
    assert loaded.confirmed is True
    assert loaded.evidence_urls == []
    assert loaded.category == "major_news"
    assert loaded.image_url is None


def test_store_round_trip_current_draft_none(tmp_path: Path):
    store = JsonStateStore(tmp_path)

    store.save_current_draft(None)

    assert store.load_current_draft() is None
    assert json.loads((tmp_path / "current_draft.json").read_text(encoding="utf-8")) is None


def test_store_loads_legacy_current_draft_with_null_image_url(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    (tmp_path / "current_draft.json").write_text(
        json.dumps(
            {
                "draft_id": "legacy-draft",
                "generated_text": "text",
                "current_text": "text",
                "selected_story_ids": ["item-1"],
                "draft_type": "digest",
                "status": "pending",
                "created_at": "2026-04-19T14:30:00+00:00",
                "approved_for_slot": True,
                "approved_at": "2026-04-19T14:45:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    loaded = store.load_current_draft()

    assert loaded.draft_id == "legacy-draft"
    assert loaded.category == "digest"
    assert loaded.header_label == "Digest"
    assert loaded.image_url is None


def test_store_migrates_legacy_approved_current_draft_to_publishing(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    (tmp_path / "current_draft.json").write_text(
        json.dumps(
            {
                "draft_id": "legacy-approved",
                "generated_text": "text",
                "current_text": "text",
                "selected_story_ids": ["item-1"],
                "draft_type": "short_post",
                "status": "pending",
                "created_at": "2026-04-19T14:30:00+00:00",
                "approved_for_slot": True,
                "approved_at": "2026-04-19T14:45:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    loaded = store.load_current_draft()

    assert loaded.draft_id == "legacy-approved"
    assert loaded.status == "publishing"


def test_store_defaults_missing_files(tmp_path: Path):
    store = JsonStateStore(tmp_path)

    assert store.load_backlog() == []
    assert store.load_current_draft() is None
    assert store.load_owner_drafts() == []
    assert store.load_published() == []
    assert store.load_cursor() == 0


def test_store_loads_published_and_cursor(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    (tmp_path / "published.json").write_text(json.dumps(["https://example.com/a"]), encoding="utf-8")
    (tmp_path / "telegram_cursor.json").write_text(
        json.dumps({"last_update_id": 41}),
        encoding="utf-8",
    )

    assert store.load_published() == ["https://example.com/a"]
    assert store.load_cursor() == 41


def test_store_rejects_malformed_payloads(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    (tmp_path / "backlog.json").write_text(json.dumps([{"item_id": "x"}]), encoding="utf-8")
    (tmp_path / "current_draft.json").write_text(json.dumps({"draft_id": "d"}), encoding="utf-8")
    (tmp_path / "published.json").write_text(json.dumps(["https://example.com/a", 1]), encoding="utf-8")
    (tmp_path / "telegram_cursor.json").write_text(json.dumps({"last_update_id": "oops"}), encoding="utf-8")

    try:
        store.load_backlog()
    except ValueError as exc:
        assert "backlog.json" in str(exc)
    else:
        raise AssertionError("Expected backlog.json validation to fail")

    try:
        store.load_current_draft()
    except ValueError as exc:
        assert "current_draft.json" in str(exc)
    else:
        raise AssertionError("Expected current_draft.json validation to fail")

    try:
        store.load_published()
    except ValueError as exc:
        assert "published.json" in str(exc)
    else:
        raise AssertionError("Expected published.json validation to fail")

    try:
        store.load_cursor()
    except ValueError as exc:
        assert "telegram_cursor.json" in str(exc)
    else:
        raise AssertionError("Expected telegram_cursor.json validation to fail")


def test_store_rejects_invalid_json(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    (tmp_path / "backlog.json").write_text("{", encoding="utf-8")

    try:
        store.load_backlog()
    except ValueError as exc:
        assert "backlog.json contains invalid JSON" in str(exc)
    else:
        raise AssertionError("Expected invalid JSON to fail")


def test_save_cursor_rejects_boolean(tmp_path: Path):
    store = JsonStateStore(tmp_path)

    try:
        store.save_cursor(True)
    except ValueError as exc:
        assert "telegram_cursor.json.last_update_id must be an integer" in str(exc)
    else:
        raise AssertionError("Expected save_cursor(True) to fail")


def test_save_published_rejects_non_string_entries(tmp_path: Path):
    store = JsonStateStore(tmp_path)

    try:
        store.save_published(["https://example.com/a", 1])
    except ValueError as exc:
        assert "published.json.1 must be a string" in str(exc)
    else:
        raise AssertionError("Expected save_published to reject non-string entries")
