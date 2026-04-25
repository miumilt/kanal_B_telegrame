from __future__ import annotations

import json
import importlib.util
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from ai_news_bot.models import BacklogItem, DraftRecord
from ai_news_bot.storage import JsonStateStore


WORKTREE_ROOT = Path(__file__).resolve().parents[1]


def _item(
    item_id: str,
    title: str,
    summary: str,
    *,
    status: str = "queued",
    category: str = "major_news",
    image_url: str | None = None,
    video_url: str | None = None,
    published_at: str = "2026-04-19T10:00:00+00:00",
) -> BacklogItem:
    return BacklogItem(
        item_id=item_id,
        source_url=f"https://example.com/{item_id}",
        source_title=title,
        normalized_title=title.lower(),
        topic_fingerprint=title.lower().replace(" ", "-"),
        source_name="Example",
        published_at=published_at,
        summary_candidate=summary,
        status=status,
        first_seen_at=published_at,
        last_considered_at=published_at,
        category=category,
        image_url=image_url,
        video_url=video_url,
    )


class FakeTelegramApi:
    def __init__(self, updates: list[dict] | None = None) -> None:
        self._updates = updates or []
        self.sent_messages: list[dict] = []
        self.sent_photos: list[dict] = []
        self.sent_videos: list[dict] = []
        self.answered_callbacks: list[dict] = []

    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        payload = {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        self.sent_messages.append(payload)
        return payload

    def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        payload = {
            "chat_id": chat_id,
            "photo_url": photo_url,
            "caption": caption,
            "reply_markup": reply_markup,
        }
        self.sent_photos.append(payload)
        return payload

    def send_video(
        self,
        chat_id: str,
        video_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        payload = {
            "chat_id": chat_id,
            "video_url": video_url,
            "caption": caption,
            "reply_markup": reply_markup,
        }
        self.sent_videos.append(payload)
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


def test_run_local_polling_script_imports_without_src_on_sys_path(monkeypatch):
    script_path = WORKTREE_ROOT / "scripts" / "run_local_polling.py"
    original_sys_path = list(sys.path)
    original_modules = dict(sys.modules)
    filtered_path = [entry for entry in sys.path if Path(entry or ".").resolve() != (WORKTREE_ROOT / "src").resolve()]

    monkeypatch.setattr(sys, "path", filtered_path)
    for module_name in list(sys.modules):
        if module_name == "poll_telegram_updates" or module_name.startswith("ai_news_bot"):
            sys.modules.pop(module_name, None)

    try:
        runpy.run_path(str(script_path), run_name="not_main")
    finally:
        sys.path[:] = original_sys_path
        sys.modules.clear()
        sys.modules.update(original_modules)


def test_local_polling_loop_calls_process_updates_repeatedly_and_stops_on_keyboard_interrupt(tmp_path: Path, monkeypatch):
    module = _load_script_module("run_local_polling")
    calls: list[int] = []
    sleeps: list[int] = []
    sync_events: list[str] = []

    def fake_process_updates(store, telegram_api, config):
        calls.append(len(calls) + 1)

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(module, "process_updates", fake_process_updates)

    module.run_local_polling(
        store=JsonStateStore(tmp_path),
        telegram_api=FakeTelegramApi(),
        config=SimpleNamespace(telegram_poll_interval_seconds=7),
        sleeper=fake_sleep,
        sync_before=lambda: sync_events.append("before"),
        sync_after=lambda: sync_events.append("after"),
    )

    assert calls == [1, 2]
    assert sleeps == [7, 7]
    assert sync_events == ["before", "after", "before", "after"]


def test_sync_repo_before_poll_autostashes_runtime_state_changes(tmp_path: Path, monkeypatch):
    module = _load_script_module("run_local_polling")
    calls: list[tuple[str, ...]] = []

    def fake_run_git(project_root: Path, *args: str):
        calls.append(args)
        return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")

    monkeypatch.setattr(module, "_run_git", fake_run_git)

    module.sync_repo_before_poll(tmp_path)

    assert calls == [("pull", "--rebase", "--autostash", "origin", "master")]


def test_run_git_includes_git_stderr_when_command_fails(tmp_path: Path, monkeypatch):
    module = _load_script_module("run_local_polling")

    def fake_subprocess_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            128,
            stdout="",
            stderr="error: cannot pull with rebase: You have unstaged changes.",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_subprocess_run)

    with pytest.raises(RuntimeError) as exc:
        module._run_git(tmp_path, "pull", "--rebase", "origin", "master")

    assert "git pull --rebase origin master failed with exit code 128" in str(exc.value)
    assert "cannot pull with rebase" in str(exc.value)


class CrashAfterChannelSendTelegramApi(FakeTelegramApi):
    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        payload = super().send_message(chat_id, text, reply_markup)
        if str(chat_id).startswith("@"):
            raise SystemExit("crashed after channel send")
        return payload

    def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        payload = super().send_photo(chat_id, photo_url, caption, reply_markup)
        if str(chat_id).startswith("@"):
            raise SystemExit("crashed after channel send")
        return payload

    def send_video(
        self,
        chat_id: str,
        video_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        payload = super().send_video(chat_id, video_url, caption, reply_markup)
        if str(chat_id).startswith("@"):
            raise SystemExit("crashed after channel send")
        return payload


class FailBeforeChannelSendTelegramApi(FakeTelegramApi):
    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        if str(chat_id).startswith("@"):
            raise RuntimeError("send failed before acceptance")
        return super().send_message(chat_id, text, reply_markup)

    def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        if str(chat_id).startswith("@"):
            raise RuntimeError("send failed before acceptance")
        return super().send_photo(chat_id, photo_url, caption, reply_markup)

    def send_video(
        self,
        chat_id: str,
        video_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        if str(chat_id).startswith("@"):
            raise RuntimeError("send failed before acceptance")
        return super().send_video(chat_id, video_url, caption, reply_markup)


class RejectMediaTelegramApi(FakeTelegramApi):
    def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        raise requests.HTTPError("telegram rejected photo")

    def send_video(
        self,
        chat_id: str,
        video_url: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        raise requests.HTTPError("telegram rejected video")


def test_daily_slot_script_builds_pending_single_post_and_notifies_owner(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.")])

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    telegram_api = FakeTelegramApi()

    draft = build_main_slot_draft(store, telegram_api=telegram_api, owner_chat_id="owner-chat")

    assert draft.status == "pending"
    assert draft.selected_story_ids == ["item-1"]
    assert draft.draft_type == "single_post"
    assert draft.current_text == draft.generated_text
    assert store.load_current_draft() == draft
    assert store.load_backlog()[0].status == "drafted"
    assert telegram_api.sent_messages == [
        {
            "chat_id": "owner-chat",
            "text": draft.generated_text,
            "reply_markup": None,
        }
    ]
    assert telegram_api.sent_photos == []


def test_daily_slot_script_sends_separate_owner_messages_for_multiple_candidates(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "Gemini CLI Released",
                "CLI tool for developers.",
                category="major_news",
                image_url="https://example.com/image-1.png",
            ),
            _item(
                "item-2",
                "Open Model Released",
                "Open weights and benchmarks.",
                category="freebie/useful_find",
            ),
            _item("item-3", "Useful Find", "A useful tool for agents."),
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    telegram_api = FakeTelegramApi()

    draft = build_main_slot_draft(store, telegram_api=telegram_api, owner_chat_id="owner-chat")

    assert draft.draft_type == "single_post"
    assert draft.selected_story_ids == ["item-1"]
    assert store.load_current_draft() == draft
    owner_drafts = store.load_owner_drafts()
    assert len(owner_drafts) == 3
    assert [item.status for item in store.load_backlog()] == ["drafted", "drafted", "drafted"]
    assert telegram_api.sent_photos == [
        {
            "chat_id": "owner-chat",
            "photo_url": "https://example.com/image-1.png",
            "caption": draft.generated_text,
            "reply_markup": None,
        }
    ]
    assert [payload["chat_id"] for payload in telegram_api.sent_messages] == ["owner-chat", "owner-chat"]
    assert "Тестим здесь: https://example.com/item-2" in telegram_api.sent_messages[0]["text"]
    assert "Где посмотреть: https://example.com/item-3" in telegram_api.sent_messages[1]["text"]
    assert telegram_api.sent_messages[0]["reply_markup"] is None
    assert telegram_api.sent_messages[1]["reply_markup"] is None


def test_daily_slot_script_sends_up_to_ten_owner_previews_without_buttons(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                f"item-{index}",
                f"AI Launch {index}",
                "A useful AI launch.",
                published_at=f"2026-04-19T10:{index:02d}:00+00:00",
            )
            for index in range(1, 13)
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    telegram_api = FakeTelegramApi()

    build_main_slot_draft(store, telegram_api=telegram_api, owner_chat_id="owner-chat")

    owner_drafts = store.load_owner_drafts()
    assert len(owner_drafts) == 10
    assert all(draft.status == "pending" for draft in owner_drafts)
    assert all(draft.selected_story_ids for draft in owner_drafts)
    assert len(telegram_api.sent_messages) == 10
    assert all(payload["reply_markup"] is None for payload in telegram_api.sent_messages)
    assert len(telegram_api.sent_photos) == 0
    assert len(telegram_api.sent_videos) == 0
    assert sum(1 for item in store.load_backlog() if item.status == "drafted") == 10
    assert sum(1 for item in store.load_backlog() if item.status == "queued") == 2


def test_daily_slot_refreshes_selected_media_from_article_page(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "GPT Image 2 Released",
                "New image model rollout.",
                image_url="https://example.com/tiny-rss-thumb.png",
            )
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    telegram_api = FakeTelegramApi()

    draft = build_main_slot_draft(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        media_refresher=lambda url: (
            "https://example.com/high-res-og-image.png",
            "https://example.com/demo.mp4",
        ),
    )

    assert draft.image_url == "https://example.com/high-res-og-image.png"
    assert draft.video_url == "https://example.com/demo.mp4"
    assert store.load_current_draft() == draft
    assert store.load_backlog()[0].image_url == "https://example.com/high-res-og-image.png"
    assert store.load_backlog()[0].video_url == "https://example.com/demo.mp4"
    assert telegram_api.sent_videos == [
        {
            "chat_id": "owner-chat",
            "video_url": "https://example.com/demo.mp4",
            "caption": draft.generated_text,
            "reply_markup": None,
        }
    ]
    assert telegram_api.sent_photos == []
    assert telegram_api.sent_messages == []


def test_daily_slot_keeps_original_media_when_article_media_refresh_fails(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "Claude Tool Released",
                "New agent feature.",
                image_url="https://example.com/feed-image.png",
            )
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft

    def failing_media_refresher(url: str) -> tuple[str | None, str | None]:
        raise RuntimeError("page fetch failed")

    telegram_api = FakeTelegramApi()

    draft = build_main_slot_draft(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        media_refresher=failing_media_refresher,
    )

    assert draft.image_url == "https://example.com/feed-image.png"
    assert draft.video_url is None
    assert telegram_api.sent_photos == [
        {
            "chat_id": "owner-chat",
            "photo_url": "https://example.com/feed-image.png",
            "caption": draft.generated_text,
            "reply_markup": None,
        }
    ]


def test_daily_slot_falls_back_to_text_when_owner_preview_photo_is_rejected(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "GPT Image 2 Released",
                "New image model rollout.",
                image_url="https://example.com/bad-image.png",
            )
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    telegram_api = RejectMediaTelegramApi()

    draft = build_main_slot_draft(store, telegram_api=telegram_api, owner_chat_id="owner-chat")

    assert telegram_api.sent_messages == [
        {
            "chat_id": "owner-chat",
            "text": draft.generated_text,
            "reply_markup": None,
        }
    ]
    assert store.load_current_draft() == draft


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
    assert draft.draft_type == "single_post"
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


def test_refresh_backlog_drops_items_older_than_two_weeks(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "expired-item",
                "Expired Story",
                "Too old to keep.",
                published_at="2026-04-01T10:00:00+00:00",
            )
        ]
    )
    module = _load_script_module("run_daily_slot")

    refreshed = module.refresh_backlog(
        store,
        now_iso="2026-04-22T10:00:00+00:00",
        fetcher=lambda now_iso: [],
    )

    assert refreshed == []
    assert store.load_backlog() == []


def test_news_watcher_sends_fresh_items_and_records_sent_topics(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    module = _load_script_module("run_news_watcher")
    telegram_api = FakeTelegramApi()

    sent = module.run_news_watcher(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        now_iso="2026-04-20T10:30:00+00:00",
        fetcher=lambda now_iso: [
            _item(
                "item-1",
                "OpenAI releases GPT-5.5",
                "The model is better at coding and agents.",
                published_at="2026-04-20T10:20:00+00:00",
            )
        ],
        preview_limit=3,
        max_age_hours=2,
    )

    assert [item.item_id for item in sent] == ["item-1"]
    assert store.load_backlog()[0].status == "published"
    assert store.load_published() == ["https://example.com/item-1"]
    assert store.load_sent_topics() == ["openai-releases-gpt-5.5"]
    assert telegram_api.sent_messages[0]["chat_id"] == "owner-chat"
    assert telegram_api.sent_messages[0]["reply_markup"] is None


def test_news_watcher_skips_already_sent_topics(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_sent_topics(["openai-releases-gpt-5.5"])
    module = _load_script_module("run_news_watcher")
    telegram_api = FakeTelegramApi()

    sent = module.run_news_watcher(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        now_iso="2026-04-20T10:30:00+00:00",
        fetcher=lambda now_iso: [
            _item(
                "item-1",
                "OpenAI releases GPT-5.5",
                "The model is better at coding and agents.",
                published_at="2026-04-20T10:20:00+00:00",
            )
        ],
        preview_limit=3,
        max_age_hours=2,
    )

    assert sent == []
    assert telegram_api.sent_messages == []


def test_daily_slot_run_only_selects_items_from_last_day(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    module = _load_script_module("run_daily_slot")
    telegram_api = FakeTelegramApi()

    draft = module.run_daily_slot(
        store,
        telegram_api=telegram_api,
        owner_chat_id="owner-chat",
        now_iso="2026-04-22T10:00:00+00:00",
        fetcher=lambda now_iso: [
            _item(
                "stale-item",
                "Stale Story",
                "Older than one day, but still within backlog retention.",
                published_at="2026-04-20T09:00:00+00:00",
            )
        ],
    )

    assert draft is None
    backlog = store.load_backlog()
    assert len(backlog) == 1
    assert backlog[0].item_id == "stale-item"
    assert backlog[0].status == "queued"
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
            category="short_post",
            header_label="Short Post",
            image_url=None,
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
        {"callback_query_id": "cb-publish", "text": "Draft published immediately"},
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


def test_process_updates_publish_now_publishes_draft_immediately(tmp_path: Path):
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
                    "id": "cb-publish",
                    "data": f"publish_now:{draft.draft_id}",
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
    assert current.status == "published"
    assert store.load_cursor() == 21
    assert store.load_published() == ["https://example.com/item-1"]
    assert telegram_api.answered_callbacks == [
        {"callback_query_id": "cb-publish", "text": "Draft published immediately"},
    ]
    assert telegram_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": draft.generated_text,
            "reply_markup": None,
        }
    ]


def test_process_updates_can_publish_non_primary_owner_preview(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item("item-1", "Gemini CLI Released", "CLI tool for developers."),
            _item("item-2", "OpenAI Privacy Filter", "Detects and redacts PII."),
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    build_main_slot_draft(store)
    owner_drafts = store.load_owner_drafts()
    second_draft = owner_drafts[1]

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 22,
                "callback_query": {
                    "id": "cb-publish-second",
                    "data": f"publish_now:{second_draft.draft_id}",
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
    assert current.draft_id == second_draft.draft_id
    assert current.status == "published"
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "drafted"
    assert backlog["item-2"].status == "published"
    assert store.load_published() == ["https://example.com/item-2"]
    assert telegram_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": second_draft.generated_text,
            "reply_markup": None,
        }
    ]


def test_process_updates_publish_now_uses_photo_when_draft_has_image(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "Gemini CLI Released",
                "CLI tool for developers.",
                category="freebie/useful_find",
                image_url="https://example.com/preview.png",
            )
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    draft = build_main_slot_draft(store)
    current = store.load_current_draft()
    assert current is not None
    assert current.category == "freebie/useful_find"
    assert current.image_url == "https://example.com/preview.png"

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 24,
                "callback_query": {
                    "id": "cb-publish-photo",
                    "data": f"publish_now:{draft.draft_id}",
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

    assert telegram_api.sent_photos == [
        {
            "chat_id": "@channel",
            "photo_url": "https://example.com/preview.png",
            "caption": draft.current_text,
            "reply_markup": None,
        }
    ]
    assert telegram_api.sent_messages == []


def test_process_updates_publish_now_prefers_video_when_draft_has_video(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "GPT Image 2 Released",
                "New image and video model demo.",
                image_url="https://example.com/preview.png",
                video_url="https://example.com/demo.mp4",
            )
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    draft = build_main_slot_draft(store)
    current = store.load_current_draft()
    assert current is not None
    assert current.image_url == "https://example.com/preview.png"
    assert current.video_url == "https://example.com/demo.mp4"

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 25,
                "callback_query": {
                    "id": "cb-publish-video",
                    "data": f"publish_now:{draft.draft_id}",
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

    assert telegram_api.sent_videos == [
        {
            "chat_id": "@channel",
            "video_url": "https://example.com/demo.mp4",
            "caption": draft.current_text,
            "reply_markup": None,
        }
    ]
    assert telegram_api.sent_photos == []
    assert telegram_api.sent_messages == []


def test_process_updates_publish_now_falls_back_to_text_when_photo_is_rejected(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "Gemini CLI Released",
                "CLI tool for developers.",
                image_url="https://example.com/rejected-preview.png",
            )
        ]
    )

    build_main_slot_draft = _load_script_module("run_daily_slot").build_main_slot_draft
    process_updates = _load_script_module("poll_telegram_updates").process_updates

    draft = build_main_slot_draft(store)
    telegram_api = RejectMediaTelegramApi(
        updates=[
            {
                "update_id": 26,
                "callback_query": {
                    "id": "cb-publish-rejected-photo",
                    "data": f"publish_now:{draft.draft_id}",
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
    assert current.status == "published"
    assert telegram_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": draft.current_text,
            "reply_markup": None,
        }
    ]
    assert store.load_published() == ["https://example.com/item-1"]


def test_process_updates_completes_legacy_approved_draft_on_next_poll(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.", status="drafted")])
    (tmp_path / "current_draft.json").write_text(
        json.dumps(
            {
                "draft_id": "legacy-approved",
                "generated_text": "Legacy approved text",
                "current_text": "Legacy approved text",
                "selected_story_ids": ["item-1"],
                "draft_type": "short_post",
                "status": "pending",
                "created_at": "2026-04-19T12:00:00+00:00",
                "approved_for_slot": True,
                "approved_at": "2026-04-19T12:30:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi()
    config = SimpleNamespace(
        telegram_owner_chat_id="owner-chat",
        telegram_channel_id="@channel",
        daily_slot_hour=18,
        daily_slot_minute=0,
    )

    process_updates(store, telegram_api, config)

    current = store.load_current_draft()
    assert current is not None
    assert current.status == "published"
    assert store.load_published() == ["https://example.com/item-1"]
    assert telegram_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": "Legacy approved text",
            "reply_markup": None,
        }
    ]


def test_process_updates_short_command_leaves_draft_pending_until_publish_now(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "Gemini CLI Released",
                "CLI tool for developers.",
                category="freebie/useful_find",
                image_url="https://example.com/preview.png",
            )
        ]
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 22,
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
    assert current.status == "pending"
    assert current.category == "freebie/useful_find"
    assert current.image_url == "https://example.com/preview.png"
    assert store.load_published() == []
    assert telegram_api.sent_messages == []
    assert telegram_api.sent_photos == [
        {
            "chat_id": "owner-chat",
            "photo_url": "https://example.com/preview.png",
            "caption": current.generated_text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "Edit", "callback_data": f"edit:{current.draft_id}"},
                        {"text": "Publish now", "callback_data": f"publish_now:{current.draft_id}"},
                        {"text": "Skip", "callback_data": f"skip:{current.draft_id}"},
                    ]
                ]
            },
        }
    ]


def test_process_updates_publish_now_command_publishes_immediately(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog([_item("item-1", "Gemini CLI Released", "CLI tool for developers.")])

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 23,
                "message": {
                    "text": "/publish_now item-1",
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
    assert current.status == "published"
    assert store.load_published() == ["https://example.com/item-1"]
    assert telegram_api.sent_messages == [
        {
            "chat_id": "@channel",
            "text": current.current_text,
            "reply_markup": None,
        }
    ]


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
            category="short_post",
            header_label="Short Post",
            image_url=None,
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
    backlog = {item.item_id: item for item in store.load_backlog()}
    assert backlog["item-1"].status == "queued"
    assert backlog["item-2"].status == "drafted"
    assert store.load_cursor() == 33
    assert telegram_api.sent_messages == []
    assert telegram_api.answered_callbacks == []


def test_process_updates_answers_stale_callbacks_for_published_draft(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Published text",
            current_text="Published text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="published",
            created_at="2026-04-19T12:00:00+00:00",
            category="short_post",
            header_label="Short Post",
            image_url=None,
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 34,
                "callback_query": {
                    "id": "cb-stale",
                    "data": f"skip:draft-existing",
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

    assert telegram_api.answered_callbacks == [
        {"callback_query_id": "cb-stale", "text": "Draft already published"},
    ]


def test_process_updates_answers_stale_callbacks_for_skipped_draft(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Skipped text",
            current_text="Skipped text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="skipped",
            created_at="2026-04-19T12:00:00+00:00",
            category="short_post",
            header_label="Short Post",
            image_url=None,
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 35,
                "callback_query": {
                    "id": "cb-stale-skip",
                    "data": f"edit:draft-existing",
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

    assert telegram_api.answered_callbacks == [
        {"callback_query_id": "cb-stale-skip", "text": "Draft already skipped"},
    ]


def test_process_updates_acknowledges_legacy_approve_callback(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Pending text",
            current_text="Pending text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            category="short_post",
            header_label="Short Post",
            image_url=None,
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    telegram_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 36,
                "callback_query": {
                    "id": "cb-legacy-approve",
                    "data": f"approve:draft-existing",
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
    assert current.status == "pending"
    assert telegram_api.answered_callbacks == [
        {
            "callback_query_id": "cb-legacy-approve",
            "text": "Scheduled approval is no longer supported; use Publish now",
        },
    ]
    assert telegram_api.sent_messages == []


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
            category="short_post",
            header_label="Short Post",
            image_url=None,
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
    store.save_backlog(
        [
            _item(
                "item-1",
                "Gemini CLI Released",
                "CLI tool for developers.",
                status="drafted",
                image_url="https://example.com/crash-preview.png",
            )
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            category="short_post",
            header_label="Short Post",
            image_url="https://example.com/crash-preview.png",
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    crashing_api = CrashAfterChannelSendTelegramApi(
        updates=[
            {
                "update_id": 91,
                "callback_query": {
                    "id": "cb-publish",
                    "data": "publish_now:draft-existing",
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

    try:
        process_updates(store, crashing_api, config)
    except SystemExit as exc:
        assert str(exc) == "crashed after channel send"
    else:
        raise AssertionError("expected publish crash")

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.status == "publishing"
    assert crashing_api.sent_messages == []
    assert crashing_api.sent_photos == [
        {
            "chat_id": "@channel",
            "photo_url": "https://example.com/crash-preview.png",
            "caption": "Approved text",
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
    assert recovery_api.sent_photos == []


def test_publish_failure_before_acceptance_reverts_out_of_publishing_for_safe_retry(tmp_path: Path):
    store = JsonStateStore(tmp_path)
    store.save_backlog(
        [
            _item(
                "item-1",
                "Gemini CLI Released",
                "CLI tool for developers.",
                status="drafted",
                image_url="https://example.com/fail-preview.png",
            )
        ]
    )
    store.save_current_draft(
        DraftRecord(
            draft_id="draft-existing",
            generated_text="Generated text",
            current_text="Approved text",
            selected_story_ids=["item-1"],
            draft_type="short_post",
            status="pending",
            created_at="2026-04-19T12:00:00+00:00",
            category="short_post",
            header_label="Short Post",
            image_url="https://example.com/fail-preview.png",
        )
    )

    process_updates = _load_script_module("poll_telegram_updates").process_updates

    failing_api = FailBeforeChannelSendTelegramApi(
        updates=[
            {
                "update_id": 92,
                "callback_query": {
                    "id": "cb-publish",
                    "data": "publish_now:draft-existing",
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
    assert failing_api.sent_photos == []

    recovery_api = FakeTelegramApi(
        updates=[
            {
                "update_id": 93,
                "callback_query": {
                    "id": "cb-retry",
                    "data": "publish_now:draft-existing",
                    "message": {"chat": {"id": "owner-chat"}},
                },
            }
        ]
    )
    process_updates(store, recovery_api, config)

    draft = store.load_current_draft()
    assert draft is not None
    assert draft.status == "published"
    assert store.load_published() == ["https://example.com/item-1"]
    assert recovery_api.sent_messages == []
    assert recovery_api.sent_photos == [
        {
            "chat_id": "@channel",
            "photo_url": "https://example.com/fail-preview.png",
            "caption": "Approved text",
            "reply_markup": None,
        }
    ]
    assert recovery_api.answered_callbacks == [
        {"callback_query_id": "cb-retry", "text": "Draft published immediately"},
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
            category="short_post",
            header_label="Short Post",
            image_url=None,
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
            category="short_post",
            header_label="Short Post",
            image_url=None,
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
            category="short_post",
            header_label="Short Post",
            image_url=None,
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


