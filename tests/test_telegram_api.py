from __future__ import annotations

from typing import Any

import pytest
import requests

from ai_news_bot.telegram_api import TelegramApi


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("request failed", response=self)

    def json(self) -> dict[str, Any]:
        return self._payload


def test_answer_callback_ignores_expired_callback_query(monkeypatch: pytest.MonkeyPatch) -> None:
    api = TelegramApi("token")

    def fake_post(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(
            status_code=400,
            payload={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: query is too old and response timeout expired or query ID is invalid",
            },
        )

    monkeypatch.setattr(requests, "post", fake_post)

    api.answer_callback("callback-id", "Draft will publish immediately")


def test_answer_callback_still_raises_for_unrelated_bad_request(monkeypatch: pytest.MonkeyPatch) -> None:
    api = TelegramApi("token")

    def fake_post(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(
            status_code=400,
            payload={
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: chat not found",
            },
        )

    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(requests.HTTPError):
        api.answer_callback("callback-id", "Draft will publish immediately")
