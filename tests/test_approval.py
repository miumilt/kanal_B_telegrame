import pytest

from ai_news_bot.approval import build_draft_keyboard, parse_owner_command
from ai_news_bot.telegram_api import TelegramApi


def test_build_draft_keyboard_uses_current_button_model():
    keyboard = build_draft_keyboard("draft-123")

    assert keyboard == {
        "inline_keyboard": [
            [
                {"text": "Edit", "callback_data": "edit:draft-123"},
                {"text": "Publish now", "callback_data": "publish_now:draft-123"},
                {"text": "Skip", "callback_data": "skip:draft-123"},
            ]
        ]
    }


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
