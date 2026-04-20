import pytest

from ai_news_bot.approval import build_draft_keyboard, parse_owner_command, should_publish_now
from ai_news_bot.telegram_api import TelegramApi


def test_build_draft_keyboard_uses_current_button_model():
    keyboard = build_draft_keyboard("draft-123")

    assert keyboard == {
        "inline_keyboard": [
            [
                {"text": "Edit", "callback_data": "edit:draft-123"},
                {"text": "Approve for 18:00", "callback_data": "approve:draft-123"},
                {"text": "Publish now", "callback_data": "publish_now:draft-123"},
                {"text": "Skip", "callback_data": "skip:draft-123"},
            ]
        ]
    }


def test_should_publish_now_waits_for_next_eligible_slot_when_before_1800():
    assert should_publish_now(
        approved_at_iso="2026-04-19T14:40:00+00:00",
        now_iso="2026-04-19T14:50:00+00:00",
        slot_hour=18,
        slot_minute=0,
    ) is False


def test_should_publish_now_releases_at_or_after_same_day_slot():
    assert should_publish_now(
        approved_at_iso="2026-04-19T14:40:00+00:00",
        now_iso="2026-04-19T15:00:00+00:00",
        slot_hour=15,
        slot_minute=0,
    ) is True


def test_should_publish_now_waits_until_next_day_when_approved_after_slot():
    assert should_publish_now(
        approved_at_iso="2026-04-19T18:30:00+03:00",
        now_iso="2026-04-19T21:00:00+03:00",
        slot_hour=18,
        slot_minute=0,
    ) is False


def test_should_publish_now_releases_on_next_days_slot_after_late_approval():
    assert should_publish_now(
        approved_at_iso="2026-04-19T18:30:00+03:00",
        now_iso="2026-04-20T18:00:00+03:00",
        slot_hour=18,
        slot_minute=0,
    ) is True


def test_parse_owner_command_extracts_supported_commands():
    assert parse_owner_command("/backlog") == ("backlog", None)
    assert parse_owner_command("/backlog now") == ("backlog", None)
    assert parse_owner_command("/short item-42") == ("short", "item-42")
    assert parse_owner_command("/publish_now item-7") == ("publish_now", "item-7")


def test_parse_owner_command_rejects_backlog_near_misses():
    assert parse_owner_command("/backlogg") == ("unknown", None)
    assert parse_owner_command("/backlog123") == ("unknown", None)
    assert parse_owner_command("/backlog_now") == ("unknown", None)


class _DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_telegram_api_raises_when_telegram_returns_ok_false(monkeypatch: pytest.MonkeyPatch):
    def fake_post(*args, **kwargs):
        return _DummyResponse({"ok": False, "description": "Bad Request: chat not found"})

    monkeypatch.setattr("ai_news_bot.telegram_api.requests.post", fake_post)

    api = TelegramApi("token")

    with pytest.raises(RuntimeError, match="Bad Request: chat not found"):
        api.send_message("@channel", "hello")
