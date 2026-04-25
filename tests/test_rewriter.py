from typing import Any

import pytest
import requests

from ai_news_bot.models import BacklogItem
from ai_news_bot.rewriter import maybe_rewrite_post, rewrite_with_openrouter


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("request failed", response=self)

    def json(self) -> dict[str, Any]:
        return self._payload


def _item() -> BacklogItem:
    return BacklogItem(
        item_id="item-1",
        source_url="https://example.com/story",
        source_title="OpenAI releases GPT-5.5",
        normalized_title="openai releases gpt-5.5",
        topic_fingerprint="topic:openai:gpt-5.5:release",
        source_name="OpenAI",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="The model is stronger at coding and agentic tasks.",
        status="queued",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
    )


def test_rewrite_with_openrouter_sends_chat_completion_request(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_post(*args: Any, **kwargs: Any) -> _FakeResponse:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeResponse(
            status_code=200,
            payload={"choices": [{"message": {"content": "Готовый пост\nГде посмотреть: https://example.com/story"}}]},
        )

    monkeypatch.setattr(requests, "post", fake_post)

    text = rewrite_with_openrouter(_item(), "fallback", api_key="key", model="test/model")

    assert text == "Готовый пост\nГде посмотреть: https://example.com/story"
    assert captured["args"] == ("https://openrouter.ai/api/v1/chat/completions",)
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer key"
    assert captured["kwargs"]["json"]["model"] == "test/model"


def test_maybe_rewrite_post_falls_back_without_key():
    assert maybe_rewrite_post(_item(), "fallback", api_key=None) == "fallback"


def test_maybe_rewrite_post_falls_back_when_openrouter_fails(monkeypatch: pytest.MonkeyPatch):
    def fake_post(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(status_code=500, payload={})

    monkeypatch.setattr(requests, "post", fake_post)

    assert maybe_rewrite_post(_item(), "fallback", api_key="key") == "fallback"
