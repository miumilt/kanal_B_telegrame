from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from ai_news_bot.models import BacklogItem, DraftRecord
from ai_news_bot.storage import JsonStateStore


WORKTREE_ROOT = Path(__file__).resolve().parents[1]


def _item(item_id: str, title: str, summary: str, *, status: str = "queued") -> BacklogItem:
    return BacklogItem(
        item_id=item_id,
        source_url=f"https://example.com/{item_id}",
        source_title=title,
        normalized_title=title.lower(),
        topic_fingerprint=title.lower().replace(" ", "-"),
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate=summary,
        status=status,
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )


class FakeTelegramApi:
    def __init__(self, updates: list[dict] | None = None) -> None:
        self._updates = updates or []
        self.sent_messages: list[dict] = []
        self.answered_callbacks: list[dict] = []

    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        payload = {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        self.sent_messages.append(payload)
        return payload

    def get_updates(self, offset: int) -> list[dict]:
        return [update for update in self._updates if update["update_id"] >= offset]

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        self.answered_callbacks.append({"callback_query_id": callback_query_id, "text": text})


def _load_script_module(module_name: str):
    module_path = WORKTREE_ROOT / "scripts" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"tests.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load script module: {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CrashAfterChannelSendTelegramApi(FakeTelegramApi):
    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        payload = super().send_message(chat_id, text, reply_markup)
        if str(chat_id).startswith("@"):
            raise SystemExit("crashed after channel send")
        return payload


class FailBeforeChannelSendTelegramApi(FakeTelegramApi):
    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        if str(chat_id).startswith("@"):
            raise RuntimeError("send failed before acceptance")
        return super().send_message(chat_id, text, reply_markup)


def test_daily_slot_script_builds_pending_short_post_and_notifies_owner(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.")])

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    telegram_api = FakeTelegramApi()

    draft = build_main_slot_draft(store, telegram_api=telegram_api, owner_chat_id="owner-chat")

    assert draft.status == "pending"
    assert draft.selected_story_ids == ["item-1"]
    assert draft.draft_type == "short_post"
    assert draft.current_text == draft.generated_text
    assert store.load_current_draft() == draft
    assert store.load_backlog()[0].status == "drafted"
    assert telegram_api.sent_messages == [
        {
            "chat_id": "owner-chat",
            "text": draft.generated_text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "Edit", "callback_data": f"edit:{draft.draft_id}"},
                        {"text": "Approve for 18:00", "callback_data": f"approve:{draft.draft_id}"},
                        {"text": "Publish now", "callback_data": f"publish_now:{draft.draft_id}"},
                        {"text": "Skip", "callback_data": f"skip:{draft.draft_id}"},
                    ]
                ]
            },
        }
    ]


def test_daily_slot_script_builds_digest_when_multiple_items_selected(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks."),
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    draft = build_main_slot_draft(store)

    assert draft.draft_type == "digest"
    assert set(draft.selected_story_ids) == {"item-1", "item-2"}
    assert "Daily AI digest for the channel:" in draft.generated_text


def test_daily_slot_run_refreshes_backlog_before_building_first_draft(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    module = _load_script_module("run_daily_slot")
    telegram_api = FakeTelegramApi()

    draft = module.run_daily_slot(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        now_iso="2026-04-20T10:00:00+00:00",
        fetcher=lambda now_iso: [_item("item-1", "Gemini CLI Released", "CLI tool for developers.")],
    )

    assert draft is not None
    assert draft.draft_type == "short_post"
    assert draft.selected_story_ids == ["item-1"]
    assert store.load_backlog()[0].status == "drafted"
    assert telegram_api.sent_messages[0]["chat_id"] == "owner-chat"


def test_daily_slot_run_skips_cleanly_when_no_eligible_items_exist(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    module = _load_script_module("run_daily_slot")
    telegram_api = FakeTelegramApi()

    draft = module.run_daily_slot(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        now_iso="2026-04-20T10:00:00+00:00",
        fetcher=lambda now_iso: [],
    )

    assert draft is None
    assert store.load_current_draft() is None
    assert store.load_backlog() == []
    assert telegram_api.sent_messages == [
        {
            "chat_id": "owner-chat",
            "text": "No eligible backlog items for draft today.",
            "reply_markup": None,
        }
    ]


def test_daily_slot_run_does_not_build_draft_from_unconfirmed_community_only_items(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    module = _load_script_module("run_daily_slot")
    telegram_api = FakeTelegramApi()

    draft = module.run_daily_slot(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        now_iso="2026-04-20T10:00:00+00:00",
        fetcher=lambda now_iso: [
            BacklogItem(
                item_id="community",
                source_url="https://example.com/hn-thread",
                source_title="Unconfirmed AI launch",
                normalized_title="unconfirmed ai launch",
                topic_fingerprint="unconfirmed-ai-launch",
                source_name="HN",
                published_at="2026-04-20T09:00:00+00:00",
                summary_candidate="discussion",
                status="observed_unconfirmed",
                first_seen_at="2026-04-20T09:00:00+00:00",
                last_considered_at="2026-04-20T09:00:00+00:00",
                source_tier="tier4_community",
                source_kind="rss",
                source_priority=4,
                confirmed=False,
                evidence_urls=["https://example.com/hn-thread"],
            )
        ],
    )

    assert draft is None
    assert "No eligible backlog items for draft today." in telegram_api.sent_messages[0]["text"]


def test_process_updates_handles_edit_backlog_short_publish_and_cursor_persistence(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks.", status="drafted"),
        ]
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Edited draft text",
            current_text="Edited draft text",
            selected_story_ids=["item-2"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at=None,
        )
    )

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 11,
                "message": {
                    "text": "/backlog",
                    "chat": {"id": "owner-chat"},
                },
            },
            {
                "update_id": 12,
                "message": {
                    "text": "/short item-1",
                    "chat": {"id": "owner-chat"},
                },
            },
            {
                "update_id": 13,
                "callback_query": {
                    "id": "cb-edit",
                    "data": "edit:short-item-1",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
            {
                "update_id": 14,
                "message": {
                    "text": "Owner revised text",
                    "chat": {"id": "owner-chat"},
                },
            },
            {
                "update_id": 15,
                "callback_query": {
                    "id": "cb-publish",
                    "data": "publish_now:short-item-1",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.current_text == "Owner revised text"
    assert draft.status == "published"
    assert store.load_cursor() == 15
    assert store.load_published() == ["https://example.com/item-1"]
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "published"
    assert backlog["item-2"].status == "queued"
    assert telegram_api.answered_callbacks == [
        {"callback_query_id": "cb-edit", "text": "Send replacement text as the next message"},
        {"callback_query_id": "cb-publish", "text": "Draft will publish immediately"},
    ]
    assert telegram_api.sent_messages[0]["chat_id"] == "owner-chat"
    assert "item-1: Gemini CLI Released" in telegram_api.sent_messages[0]["text"]
    assert telegram_api.sent_messages[1]["chat_id"] == "owner-chat"
    assert telegram_api.sent_messages[1]["reply_markup"] is not None
    assert telegram_api.sent_messages[2]["text"] == "Draft updated. You can publish or edit again."
    assert telegram_api.sent_messages[3] == {
        "chat_id": "@channel",
        "text": "Owner revised text",
        "reply_markup": None,
    }


def test_process_updates_approves_for_slot_and_skip_leaves_draft_unpublished(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.")])

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    draft = build_main_slot_draft(store)
    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 21,
                "callback_query": {
                    "id": "cb-approve",
                    "data": f"approve:{draft.draft_id}",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
            {
                "update_id": 22,
                "callback_query": {
                    "id": "cb-skip",
                    "data": f"skip:{draft.draft_id}",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    current = store.load_current_draft()
    assert current is not None
    assert current.approved_at is None
    assert current.approved_for_slot is False
    assert current.status == "skipped"
    assert store.load_cursor() == 22
    assert store.load_published() == []
    assert telegram_api.answered_callbacks == [
        {"callback_query_id": "cb-approve", "text": "Draft approved for 18:00"},
        {"callback_query_id": "cb-skip", "text": "Draft skipped"},
    ]
    assert telegram_api.sent_messages == []


def test_process_updates_ignores_messages_and_callbacks_from_non_owner(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks.", status="drafted"),
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Existing draft text",
            current_text="Existing draft text",
            selected_story_ids=["item-2"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at=None,
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 31,
                "message": {
                    "text": "/short item-1",
                    "chat": {"id": "intruder-chat"},
                },
            },
            {
                "update_id": 32,
                "callback_query": {
                    "id": "cb-intruder",
                    "data": "publish_now:draft-existing",
                    "message": {"chat": {"id": "intruder-chat"}},
                },
            },
            {
                "update_id": 33,
                "message": {
                    "text": "Malicious replacement",
                    "chat": {"id": "intruder-chat"},
                },
            },
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.current_text == "Existing draft text"
    assert draft.status == "pending"
    assert draft.approved_at is None
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "queued"
    assert backlog["item-2"].status == "drafted"
    assert store.load_cursor() == 33
    assert telegram_api.sent_messages == []
    assert telegram_api.answered_callbacks == []


def test_short_draft_replacement_restores_previous_draft_items_to_queued(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks.", status="drafted"),
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Existing digest",
            current_text="Existing digest",
            selected_story_ids=["item-2"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at=None,
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 41,
                "message": {
                    "text": "/short item-1",
                    "chat": {"id": "owner-chat"},
                },
            }
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.draft_id == "short-item-1"
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "drafted"
    assert backlog["item-2"].status == "queued"


def test_skip_restores_unpublished_draft_items_to_queued(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.")])

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    draft = build_main_slot_draft(store)
    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 51,
                "callback_query": {
                    "id": "cb-skip",
                    "data": f"skip:{draft.draft_id}",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            }
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    current = store.load_current_draft()
    assert current is not None
    assert current.status == "skipped"
    assert store.load_backlog()[0].status == "queued"
    assert store.load_published() == []


def test_publish_recovery_finalizes_without_duplicate_send_after_post_send_crash(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.", status="drafted")])
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at="2026-04-19T12:10:00+00:00",
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    crashing_api = CrashAfterChannelSendTelegramApi()
    try:
        process_updates(store, crashing_api, config)
    except SystemExit as exc:
        assert str(exc) == "crashed after channel send"
    else:
        raise AssertionError("expected publish crash")

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.status == "publishing"
    assert crashing_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": "Approved text",
            "reply_markup": None,
        }
    ]

    recovery_api = FakeTelegramApi()
    process_updates(store, recovery_api, config)

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.status == "published"
    assert store.load_published() == ["https://example.com/item-1"]
    assert store.load_backlog()[0].status == "published"
    assert recovery_api.sent_messages == []


def test_publish_failure_before_acceptance_reverts_out_of_publishing_for_safe_retry(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.", status="drafted")])
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at="2026-04-19T12:10:00+00:00",
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    failing_api = FailBeforeChannelSendTelegramApi()
    try:
        process_updates(store, failing_api, config)
    except RuntimeError as exc:
        assert str(exc) == "send failed before acceptance"
    else:
        raise AssertionError("expected send failure")

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.status == "pending"
    assert store.load_published() == []
    assert store.load_backlog()[0].status == "drafted"
    assert failing_api.sent_messages == []

    recovery_api = FakeTelegramApi()
    process_updates(store, recovery_api, config)

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.status == "published"
    assert store.load_published() == ["https://example.com/item-1"]
    assert recovery_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": "Approved text",
            "reply_markup": None,
        }
    ]


def test_daily_slot_build_does_not_replace_publishing_draft(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks.", status="drafted"),
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-2"],
            draft_type="short_post",
            status="publishing",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at="2026-04-19T12:10:00+00:00",
        )
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    try:
        build_main_slot_draft(store)
    except RuntimeError as exc:
        assert str(exc) == "Cannot replace draft while publication recovery is pending"
    else:
        raise AssertionError("expected publishing draft to be protected")

    current = store.load_current_draft()
    assert current is not None
    assert current.status == "publishing"
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "queued"
    assert backlog["item-2"].status == "drafted"


def test_short_command_does_not_replace_publishing_draft(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks.", status="drafted"),
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-2"],
            draft_type="short_post",
            status="publishing",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at="2026-04-19T12:10:00+00:00",
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 61,
                "message": {
                    "text": "/short item-1",
                    "chat": {"id": "owner-chat"},
                },
            }
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    current = store.load_current_draft()
    assert current is not None
    assert current.draft_id == "draft-existing"
    assert current.status == "published"
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "queued"
    assert backlog["item-2"].status == "published"
    assert telegram_api.sent_messages == []


def test_callback_actions_are_ignored_while_draft_is_publishing(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.", status="drafted")])
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="publishing",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=False,
            approved_at="2026-04-19T12:10:00+00:00",
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 71,
                "callback_query": {
                    "id": "cb-edit",
                    "data": "edit:draft-existing",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
            {
                "update_id": 72,
                "callback_query": {
                    "id": "cb-skip",
                    "data": "skip:draft-existing",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    current = store.load_current_draft()
    assert current is not None
    assert current.draft_id == "draft-existing"
    assert current.status == "published"
    assert telegram_api.answered_callbacks == []
    assert telegram_api.sent_messages == []
    assert store.load_backlog()[0].status == "published"


def test_daily_slot_build_does_not_replace_approved_slot_draft_before_publish(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "Open Model Released", "Open weights and benchmarks.", status="drafted"),
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-2"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            approved_for_slot=True,
            approved_at="2026-04-19T12:10:00+00:00",
        )
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    try:
        build_main_slot_draft(store)
    except RuntimeError as exc:
        assert str(exc) == "Cannot replace draft while scheduled publication is pending"
    else:
        raise AssertionError("expected approved slot draft to be protected")

    current = store.load_current_draft()
    assert current is not None
    assert current.draft_id == "draft-existing"
    assert current.status == "pending"
    assert current.approved_for_slot is True
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "queued"
    assert backlog["item-2"].status == "drafted"


def test_daily_slot_build_can_run_again_after_approved_draft_is_skipped(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.")])

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    draft = build_main_slot_draft(store)
    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 81,
                "callback_query": {
                    "id": "cb-approve",
                    "data": f"approve:{draft.draft_id}",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
            {
                "update_id": 82,
                "callback_query": {
                    "id": "cb-skip",
                    "data": f"skip:{draft.draft_id}",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            },
        ]
    )
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    skipped = store.load_current_draft()
    assert skipped is not None
    assert skipped.status == "skipped"

    replacement = build_main_slot_draft(store)

    assert replacement.draft_id != draft.draft_id
    assert replacement.status == "pending"
    assert replacement.approved_for_slot is False
    assert replacement.approved_at is None
