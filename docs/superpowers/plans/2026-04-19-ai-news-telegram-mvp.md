# AI News Telegram MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a no-cost Telegram AI news bot that accumulates English-language AI news into a backlog, drafts Russian-language posts for the daily 18:00 Moscow editorial slot, lets the owner edit drafts in Telegram, and publishes only after owner approval.

**Architecture:** Use Python with file-based JSON state committed back to the repository by GitHub Actions. A daily workflow refreshes the backlog and drafts the main-slot post, while a separate polling workflow runs every 5 minutes to process Telegram callback/button actions, capture owner edits, and publish approved posts without a permanent server.

**Tech Stack:** Python 3.12, `requests`, `feedparser`, `trafilatura`, `deep-translator`, `pytest`, GitHub Actions, Telegram Bot HTTP API

---

## Assumptions

- The repository starts effectively empty.
- No paid APIs are allowed in the MVP.
- News discovery uses broad query-based Google News RSS search plus direct article extraction, not a paid search API.
- Russian text generation in MVP uses extractive summarization plus translation, not an LLM API.
- The main draft is generated at `17:30 Europe/Moscow`.
- `Approve for 18:00` schedules publication for the next eligible `18:00 Europe/Moscow` slot.
- `Publish now` bypasses the slot and publishes immediately.
- Owner-triggered manual short-post publication outside the main slot is supported through Telegram commands handled by the polling workflow.
- Draft editing works as a two-step flow: the owner presses `Edit`, then sends a replacement message that becomes the draft's publishable text.

## File Map

### Project files

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.gitignore`

### Application package

- Create: `src/ai_news_bot/__init__.py`
- Create: `src/ai_news_bot/config.py`
- Create: `src/ai_news_bot/models.py`
- Create: `src/ai_news_bot/storage.py`
- Create: `src/ai_news_bot/queries.py`
- Create: `src/ai_news_bot/discovery.py`
- Create: `src/ai_news_bot/ranking.py`
- Create: `src/ai_news_bot/backlog.py`
- Create: `src/ai_news_bot/drafts.py`
- Create: `src/ai_news_bot/telegram_api.py`
- Create: `src/ai_news_bot/approval.py`

### Entry points and state

- Create: `scripts/run_daily_slot.py`
- Create: `scripts/poll_telegram_updates.py`
- Create: `state/.gitkeep`
- Create: `state/backlog.json`
- Create: `state/published.json`
- Create: `state/current_draft.json`
- Create: `state/telegram_cursor.json`

### CI workflows

- Create: `.github/workflows/daily_slot.yml`
- Create: `.github/workflows/poll_telegram.yml`

### Tests

- Create: `tests/test_config.py`
- Create: `tests/test_storage.py`
- Create: `tests/test_discovery.py`
- Create: `tests/test_backlog.py`
- Create: `tests/test_drafts.py`
- Create: `tests/test_approval.py`
- Create: `tests/test_scripts.py`

## Task 1: Bootstrap the Python project and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/ai_news_bot/__init__.py`
- Create: `src/ai_news_bot/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing config test**

```python
# tests/test_config.py
from pathlib import Path

from ai_news_bot.config import load_config


def test_load_config_reads_env_and_uses_defaults(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@channel")
    monkeypatch.setenv("STATE_DIR", str(tmp_path))

    config = load_config()

    assert config.telegram_bot_token == "token"
    assert config.telegram_owner_chat_id == "123"
    assert config.telegram_channel_id == "@channel"
    assert config.state_dir == tmp_path
    assert config.daily_slot_hour == 18
    assert config.daily_slot_minute == 0
    assert config.draft_generation_hour == 17
    assert config.draft_generation_minute == 30
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_config.py -q`

Expected: FAIL with `ModuleNotFoundError` for `ai_news_bot` or import errors for `load_config`.

- [ ] **Step 3: Write the minimal project bootstrap and config loader**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-news-telegram"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "requests>=2.32.0",
  "feedparser>=6.0.11",
  "trafilatura>=1.9.0",
  "deep-translator>=1.11.4",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```python
# src/ai_news_bot/config.py
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    telegram_owner_chat_id: str
    telegram_channel_id: str
    state_dir: Path
    timezone_name: str = "Europe/Moscow"
    daily_slot_hour: int = 18
    daily_slot_minute: int = 0
    draft_generation_hour: int = 17
    draft_generation_minute: int = 30


def load_config() -> AppConfig:
    return AppConfig(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_owner_chat_id=os.environ["TELEGRAM_OWNER_CHAT_ID"],
        telegram_channel_id=os.environ["TELEGRAM_CHANNEL_ID"],
        state_dir=Path(os.environ.get("STATE_DIR", "state")),
    )
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_config.py -q`

Expected: PASS with `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/ai_news_bot/__init__.py src/ai_news_bot/config.py tests/test_config.py
git commit -m "chore: bootstrap python project and config loader"
```

## Task 2: Implement JSON state storage and domain models

**Files:**
- Create: `src/ai_news_bot/models.py`
- Create: `src/ai_news_bot/storage.py`
- Create: `state/backlog.json`
- Create: `state/published.json`
- Create: `state/current_draft.json`
- Create: `state/telegram_cursor.json`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write the failing storage tests**

```python
# tests/test_storage.py
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
    )
    draft = DraftRecord(
        draft_id="draft-1",
        generated_text="text",
        current_text="text",
        selected_story_ids=["item-1"],
        draft_type="digest",
        status="pending",
        created_at="2026-04-19T14:30:00+00:00",
        approved_for_slot=False,
        approved_at=None,
    )

    store.save_backlog([item])
    store.save_current_draft(draft)

    assert store.load_backlog()[0].item_id == "item-1"
    assert store.load_current_draft().draft_id == "draft-1"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_storage.py -q`

Expected: FAIL with import errors for `BacklogItem`, `DraftRecord`, or `JsonStateStore`.

- [ ] **Step 3: Write the models and JSON store**

```python
# src/ai_news_bot/models.py
from dataclasses import asdict, dataclass


@dataclass
class BacklogItem:
    item_id: str
    source_url: str
    source_title: str
    normalized_title: str
    topic_fingerprint: str
    source_name: str
    published_at: str
    summary_candidate: str
    status: str
    first_seen_at: str
    last_considered_at: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DraftRecord:
    draft_id: str
    generated_text: str
    current_text: str
    selected_story_ids: list[str]
    draft_type: str
    status: str
    created_at: str
    approved_for_slot: bool
    approved_at: str | None

    def to_dict(self) -> dict:
        return asdict(self)
```

```python
# src/ai_news_bot/storage.py
from __future__ import annotations

import json
from pathlib import Path

from ai_news_bot.models import BacklogItem, DraftRecord


class JsonStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.root / name

    def _read_json(self, name: str, default):
        path = self._path(name)
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, name: str, value) -> None:
        self._path(name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_backlog(self) -> list[BacklogItem]:
        raw = self._read_json("backlog.json", [])
        return [BacklogItem(**item) for item in raw]

    def save_backlog(self, items: list[BacklogItem]) -> None:
        self._write_json("backlog.json", [item.to_dict() for item in items])

    def load_current_draft(self) -> DraftRecord | None:
        raw = self._read_json("current_draft.json", None)
        return None if raw is None else DraftRecord(**raw)

    def save_current_draft(self, draft: DraftRecord | None) -> None:
        payload = None if draft is None else draft.to_dict()
        self._write_json("current_draft.json", payload)

    def load_cursor(self) -> int:
        raw = self._read_json("telegram_cursor.json", {"last_update_id": 0})
        return int(raw["last_update_id"])

    def save_cursor(self, update_id: int) -> None:
        self._write_json("telegram_cursor.json", {"last_update_id": update_id})

    def load_published(self) -> list[str]:
        return self._read_json("published.json", [])

    def save_published(self, source_urls: list[str]) -> None:
        self._write_json("published.json", source_urls)
```

```json
// state/backlog.json
[]
```

```json
// state/published.json
[]
```

```json
// state/current_draft.json
null
```

```json
// state/telegram_cursor.json
{"last_update_id": 0}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_storage.py -q`

Expected: PASS with `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/ai_news_bot/models.py src/ai_news_bot/storage.py state/backlog.json state/published.json state/current_draft.json state/telegram_cursor.json tests/test_storage.py
git commit -m "feat: add json state storage and domain models"
```

## Task 3: Implement discovery, ranking, deduplication, and backlog lifecycle

**Files:**
- Create: `src/ai_news_bot/queries.py`
- Create: `src/ai_news_bot/discovery.py`
- Create: `src/ai_news_bot/ranking.py`
- Create: `src/ai_news_bot/backlog.py`
- Create: `tests/test_discovery.py`
- Create: `tests/test_backlog.py`

- [ ] **Step 1: Write the failing discovery and backlog tests**

```python
# tests/test_discovery.py
from ai_news_bot.discovery import normalize_title


def test_normalize_title_collapses_case_and_spacing():
    assert normalize_title("  New  Gemini CLI  ") == "new gemini cli"
```

```python
# tests/test_backlog.py
from ai_news_bot.backlog import merge_candidates
from ai_news_bot.models import BacklogItem


def test_merge_candidates_skips_duplicate_title_and_expires_old_items():
    existing = [
        BacklogItem(
            item_id="old",
            source_url="https://example.com/old",
            source_title="Old Story",
            normalized_title="old story",
            topic_fingerprint="old-story",
            source_name="Example",
            published_at="2026-04-10T10:00:00+00:00",
            summary_candidate="old",
            status="queued",
            first_seen_at="2026-04-10T10:00:00+00:00",
            last_considered_at="2026-04-10T10:00:00+00:00",
        )
    ]
    incoming = [
        BacklogItem(
            item_id="new",
            source_url="https://example.com/gemini-cli",
            source_title="New Gemini CLI",
            normalized_title="new gemini cli",
            topic_fingerprint="new-gemini-cli",
            source_name="Example",
            published_at="2026-04-19T10:00:00+00:00",
            summary_candidate="new",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
        ),
        BacklogItem(
            item_id="dup",
            source_url="https://example.com/gemini-cli-dup",
            source_title="New   Gemini CLI",
            normalized_title="new gemini cli",
            topic_fingerprint="new-gemini-cli",
            source_name="Another",
            published_at="2026-04-19T11:00:00+00:00",
            summary_candidate="dup",
            status="queued",
            first_seen_at="2026-04-19T11:00:00+00:00",
            last_considered_at="2026-04-19T11:00:00+00:00",
        ),
    ]

    merged = merge_candidates(existing, incoming, now_iso="2026-04-19T12:00:00+00:00", expiry_days=4)

    assert [item.item_id for item in merged] == ["new"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_discovery.py tests/test_backlog.py -q`

Expected: FAIL with missing modules or missing `merge_candidates` / `normalize_title`.

- [ ] **Step 3: Write the discovery and backlog modules**

```python
# src/ai_news_bot/queries.py
AI_SEARCH_QUERIES = [
    "AI OR artificial intelligence OR LLM",
    "OpenAI OR Anthropic OR Google Gemini OR Claude OR xAI",
    "AI research OR benchmark OR model release",
    "AI open source OR AI tooling OR AI regulation",
]
```

```python
# src/ai_news_bot/discovery.py
from __future__ import annotations

from datetime import datetime, timezone
import re
from uuid import uuid4

import feedparser
import requests
import trafilatura

from ai_news_bot.models import BacklogItem
from ai_news_bot.queries import AI_SEARCH_QUERIES


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def build_google_news_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"


def fetch_candidates(now_iso: str) -> list[BacklogItem]:
    items: list[BacklogItem] = []
    for query in AI_SEARCH_QUERIES:
        feed = feedparser.parse(build_google_news_url(query))
        for entry in feed.entries:
            url = entry.link
            downloaded = trafilatura.fetch_url(url) or ""
            extracted = trafilatura.extract(downloaded) or entry.get("summary", "")
            title = entry.title
            items.append(
                BacklogItem(
                    item_id=str(uuid4()),
                    source_url=url,
                    source_title=title,
                    normalized_title=normalize_title(title),
                    topic_fingerprint=normalize_title(title).replace(" ", "-"),
                    source_name=getattr(entry, "source", {}).get("title", "unknown"),
                    published_at=entry.get("published", now_iso),
                    summary_candidate=extracted[:800],
                    status="new",
                    first_seen_at=now_iso,
                    last_considered_at=now_iso,
                )
            )
    return items
```

```python
# src/ai_news_bot/ranking.py
from datetime import datetime, timezone

from ai_news_bot.models import BacklogItem


KEYWORDS = {
    "release": 4,
    "launch": 4,
    "model": 3,
    "research": 3,
    "benchmark": 3,
    "funding": 2,
    "regulation": 2,
    "open source": 3,
    "cli": 2,
}


def score_item(item: BacklogItem) -> int:
    text = f"{item.source_title} {item.summary_candidate}".lower()
    score = 0
    for keyword, weight in KEYWORDS.items():
        if keyword in text:
            score += weight
    return score
```

```python
# src/ai_news_bot/backlog.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai_news_bot.models import BacklogItem
from ai_news_bot.ranking import score_item


def merge_candidates(
    existing: list[BacklogItem],
    incoming: list[BacklogItem],
    *,
    now_iso: str,
    expiry_days: int,
) -> list[BacklogItem]:
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    survivors = []
    seen_titles = set()

    for item in existing:
        published_at = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
        if now - published_at <= timedelta(days=expiry_days) and item.status not in {"published", "skipped", "expired"}:
            seen_titles.add(item.normalized_title)
            survivors.append(item)

    for item in incoming:
        if item.normalized_title in seen_titles:
            continue
        seen_titles.add(item.normalized_title)
        item.status = "queued"
        survivors.append(item)

    return sorted(survivors, key=score_item, reverse=True)


def select_main_slot_items(backlog: list[BacklogItem], limit: int = 5) -> list[BacklogItem]:
    queued = [item for item in backlog if item.status == "queued"]
    return sorted(queued, key=score_item, reverse=True)[:limit]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_discovery.py tests/test_backlog.py -q`

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/ai_news_bot/queries.py src/ai_news_bot/discovery.py src/ai_news_bot/ranking.py src/ai_news_bot/backlog.py tests/test_discovery.py tests/test_backlog.py
git commit -m "feat: add news discovery and backlog lifecycle"
```

## Task 4: Implement Russian draft building for digest and short-post modes

**Files:**
- Create: `src/ai_news_bot/drafts.py`
- Create: `tests/test_drafts.py`

- [ ] **Step 1: Write the failing draft tests**

```python
# tests/test_drafts.py
from ai_news_bot.drafts import build_digest_text, build_short_post_text
from ai_news_bot.models import BacklogItem


def test_build_digest_text_renders_multiple_items():
    items = [
        BacklogItem(
            item_id="1",
            source_url="https://example.com/1",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="Example",
            published_at="2026-04-19T10:00:00+00:00",
            summary_candidate="CLI tool for developers.",
            status="queued",
            first_seen_at="2026-04-19T10:00:00+00:00",
            last_considered_at="2026-04-19T10:00:00+00:00",
        )
    ]

    text = build_digest_text(items, translated_title=lambda s: f"RU:{s}", translated_body=lambda s: f"RU:{s}")

    assert "RU:Gemini CLI Released" in text
    assert "https://example.com/1" in text


def test_build_short_post_text_renders_single_item():
    item = BacklogItem(
        item_id="1",
        source_url="https://example.com/1",
        source_title="Gemini CLI Released",
        normalized_title="gemini cli released",
        topic_fingerprint="gemini-cli-released",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="CLI tool for developers.",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )

    text = build_short_post_text(item, translated_title=lambda s: f"RU:{s}", translated_body=lambda s: f"RU:{s}")

    assert "RU:Gemini CLI Released" in text
    assert "https://example.com/1" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_drafts.py -q`

Expected: FAIL with missing `build_digest_text` / `build_short_post_text`.

- [ ] **Step 3: Write the draft builder**

```python
# src/ai_news_bot/drafts.py
from __future__ import annotations

from deep_translator import GoogleTranslator

from ai_news_bot.models import BacklogItem


def _translate(value: str) -> str:
    return GoogleTranslator(source="en", target="ru").translate(value)


def build_digest_text(
    items: list[BacklogItem],
    *,
    translated_title=_translate,
    translated_body=_translate,
) -> str:
    parts = ["Daily AI digest for the channel:"]
    for index, item in enumerate(items, start=1):
        parts.append(
            "\n".join(
                [
                    f"{index}. {translated_title(item.source_title)}",
                    translated_body(item.summary_candidate[:280]),
                    f"Source: {item.source_url}",
                ]
            )
        )
    return "\n\n".join(parts)


def build_short_post_text(
    item: BacklogItem,
    *,
    translated_title=_translate,
    translated_body=_translate,
) -> str:
    return "\n".join(
        [
            translated_title(item.source_title),
            translated_body(item.summary_candidate[:280]),
            f"Source: {item.source_url}",
        ]
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_drafts.py -q`

Expected: PASS with `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/ai_news_bot/drafts.py tests/test_drafts.py
git commit -m "feat: add russian digest and short-post drafting"
```

## Task 5: Implement Telegram delivery, approval actions, and publish timing

**Files:**
- Create: `src/ai_news_bot/telegram_api.py`
- Create: `src/ai_news_bot/approval.py`
- Create: `tests/test_approval.py`

- [ ] **Step 1: Write the failing approval tests**

```python
# tests/test_approval.py
from ai_news_bot.approval import should_publish_now


def test_should_publish_now_waits_for_slot_before_18():
    assert should_publish_now(
        approved_at_iso="2026-04-19T14:40:00+00:00",
        now_iso="2026-04-19T14:50:00+00:00",
        slot_hour=15,
        slot_minute=0,
    ) is False


def test_should_publish_now_releases_after_slot():
    assert should_publish_now(
        approved_at_iso="2026-04-19T14:40:00+00:00",
        now_iso="2026-04-19T15:01:00+00:00",
        slot_hour=15,
        slot_minute=0,
    ) is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_approval.py -q`

Expected: FAIL with missing `should_publish_now`.

- [ ] **Step 3: Write the Telegram API wrapper and approval helpers**

```python
# src/ai_news_bot/telegram_api.py
from __future__ import annotations

import requests


class TelegramApi:
    def __init__(self, bot_token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, chat_id: str, text: str, reply_markup: dict | None = None) -> dict:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        response = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_updates(self, offset: int) -> list[dict]:
        response = requests.get(
            f"{self.base_url}/getUpdates",
            params={"offset": offset, "timeout": 0},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["result"]

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        requests.post(
            f"{self.base_url}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=30,
        ).raise_for_status()
```

```python
# src/ai_news_bot/approval.py
from __future__ import annotations

from datetime import datetime, timezone


def build_draft_keyboard(draft_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Edit", "callback_data": f"edit:{draft_id}"},
                {"text": "Approve for 18:00", "callback_data": f"approve:{draft_id}"},
                {"text": "Publish now", "callback_data": f"publish_now:{draft_id}"},
                {"text": "Skip", "callback_data": f"skip:{draft_id}"},
            ]
        ]
    }


def should_publish_now(
    *,
    approved_at_iso: str,
    now_iso: str,
    slot_hour: int,
    slot_minute: int,
) -> bool:
    approved_at = datetime.fromisoformat(approved_at_iso.replace("Z", "+00:00"))
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    slot = now.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
    if approved_at >= slot:
        return True
    return now >= slot


def mark_draft_approved(draft, approved_at_iso: str):
    draft.approved_for_slot = True
    draft.approved_at = approved_at_iso
    return draft


def mark_draft_publish_now(draft, approved_at_iso: str):
    draft.approved_for_slot = False
    draft.approved_at = approved_at_iso
    return draft


def mark_draft_editing(draft):
    draft.status = "editing"
    return draft
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_approval.py -q`

Expected: PASS with `2 passed`.

- [ ] **Step 5: Extend approval handling to cover backlog commands**

```python
# add to src/ai_news_bot/approval.py
def parse_owner_command(text: str) -> tuple[str, str | None]:
    stripped = text.strip()
    if stripped.startswith("/backlog"):
        return ("backlog", None)
    if stripped.startswith("/short "):
        return ("short", stripped.split(maxsplit=1)[1])
    if stripped.startswith("/publish_now "):
        return ("publish_now", stripped.split(maxsplit=1)[1])
    return ("unknown", None)
```

- [ ] **Step 6: Run the approval tests again and add a small parser assertion**

Add this assertion to `tests/test_approval.py`:

```python
from ai_news_bot.approval import parse_owner_command


def test_parse_owner_command_extracts_short_item_id():
    assert parse_owner_command("/short item-42") == ("short", "item-42")
```

Run: `python -m pytest tests/test_approval.py -q`

Expected: PASS with `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add src/ai_news_bot/telegram_api.py src/ai_news_bot/approval.py tests/test_approval.py
git commit -m "feat: add telegram approval and publish timing"
```

## Task 6: Wire the daily-slot script and polling script

**Files:**
- Create: `scripts/run_daily_slot.py`
- Create: `scripts/poll_telegram_updates.py`
- Create: `tests/test_scripts.py`

- [ ] **Step 1: Write the failing script orchestration test**

```python
# tests/test_scripts.py
from pathlib import Path

from ai_news_bot.models import BacklogItem
from ai_news_bot.storage import JsonStateStore


def test_daily_slot_script_builds_pending_draft(tmp_path: Path, monkeypatch):
    store = JsonStateStore(tmp_path)
    item = BacklogItem(
        item_id="item-1",
        source_url="https://example.com/story",
        source_title="Gemini CLI Released",
        normalized_title="gemini cli released",
        topic_fingerprint="gemini-cli-released",
        source_name="Example",
        published_at="2026-04-19T10:00:00+00:00",
        summary_candidate="CLI tool for developers.",
        status="queued",
        first_seen_at="2026-04-19T10:00:00+00:00",
        last_considered_at="2026-04-19T10:00:00+00:00",
    )
    store.save_backlog([item])

    from scripts.run_daily_slot import build_main_slot_draft

    draft = build_main_slot_draft(store)

    assert draft.status == "pending"
    assert draft.selected_story_ids == ["item-1"]
    assert draft.draft_type == "short_post"
    assert draft.current_text == draft.generated_text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_scripts.py -q`

Expected: FAIL with missing `build_main_slot_draft`.

- [ ] **Step 3: Write the daily draft builder script**

```python
# scripts/run_daily_slot.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ai_news_bot.approval import build_draft_keyboard
from ai_news_bot.backlog import select_main_slot_items
from ai_news_bot.drafts import build_digest_text, build_short_post_text
from ai_news_bot.models import DraftRecord


def build_main_slot_draft(store, telegram_api=None, owner_chat_id=None):
    backlog = store.load_backlog()
    selected = select_main_slot_items(backlog)
    if not selected:
        raise RuntimeError("No eligible backlog items for draft")

    if len(selected) == 1:
        text = build_short_post_text(selected[0])
        draft_type = "short_post"
    else:
        text = build_digest_text(selected[:5])
        draft_type = "digest"

    draft = DraftRecord(
        draft_id=str(uuid4()),
        generated_text=text,
        current_text=text,
        selected_story_ids=[item.item_id for item in selected[:5]],
        draft_type=draft_type,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        approved_for_slot=False,
        approved_at=None,
    )
    store.save_current_draft(draft)
    selected_ids = set(draft.selected_story_ids)
    for item in backlog:
        if item.item_id in selected_ids:
            item.status = "drafted"
    store.save_backlog(backlog)
    if telegram_api and owner_chat_id:
        telegram_api.send_message(owner_chat_id, draft.generated_text, build_draft_keyboard(draft.draft_id))
    return draft
```

- [ ] **Step 4: Write the polling script skeleton**

```python
# scripts/poll_telegram_updates.py
from __future__ import annotations

from datetime import datetime, timezone

from ai_news_bot.approval import build_draft_keyboard, mark_draft_approved, mark_draft_editing, mark_draft_publish_now, parse_owner_command, should_publish_now
from ai_news_bot.drafts import build_short_post_text
from ai_news_bot.models import DraftRecord


def process_updates(store, telegram_api, config) -> None:
    cursor = store.load_cursor()
    updates = telegram_api.get_updates(offset=cursor + 1)
    for update in updates:
        cursor = update["update_id"]
        callback = update.get("callback_query")
        message = update.get("message")
        if callback:
            data = callback["data"]
            draft = store.load_current_draft()
            if draft and data == f"approve:{draft.draft_id}":
                draft = mark_draft_approved(draft, datetime.now(timezone.utc).isoformat())
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Draft approved for 18:00")
            elif draft and data == f"publish_now:{draft.draft_id}":
                draft = mark_draft_publish_now(draft, datetime.now(timezone.utc).isoformat())
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Draft will publish immediately")
            elif draft and data == f"edit:{draft.draft_id}":
                draft = mark_draft_editing(draft)
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Send replacement text as the next message")
            elif draft and data == f"skip:{draft.draft_id}":
                draft.status = "skipped"
                store.save_current_draft(draft)
                telegram_api.answer_callback(callback["id"], "Draft skipped")
        elif message:
            draft = store.load_current_draft()
            if draft and draft.status == "editing":
                draft.current_text = message.get("text", "").strip()
                draft.status = "pending"
                store.save_current_draft(draft)
                telegram_api.send_message(
                    config.telegram_owner_chat_id,
                    "Draft updated. You can publish or edit again.",
                    build_draft_keyboard(draft.draft_id),
                )
                continue
            command, arg = parse_owner_command(message.get("text", ""))
            if command == "backlog":
                queued = [item for item in store.load_backlog() if item.status == "queued"][:10]
                lines = [f"{item.item_id}: {item.source_title}" for item in queued] or ["Backlog is empty"]
                telegram_api.send_message(config.telegram_owner_chat_id, "\n".join(lines))
            elif command == "short" and arg:
                backlog = store.load_backlog()
                item = next((entry for entry in backlog if entry.item_id == arg and entry.status in {"queued", "drafted"}), None)
                if item:
                    draft = DraftRecord(
                        draft_id=f"short-{item.item_id}",
                        generated_text=build_short_post_text(item),
                        current_text=build_short_post_text(item),
                        selected_story_ids=[item.item_id],
                        draft_type="short_post",
                        status="pending",
                        created_at=datetime.now(timezone.utc).isoformat(),
                        approved_for_slot=False,
                        approved_at=None,
                    )
                    store.save_current_draft(draft)
                    telegram_api.send_message(
                        config.telegram_owner_chat_id,
                        draft.generated_text,
                        build_draft_keyboard(draft.draft_id),
                    )
            elif command == "publish_now":
                draft = store.load_current_draft()
                if draft:
                    draft = mark_draft_publish_now(draft, datetime.now(timezone.utc).isoformat())
                    store.save_current_draft(draft)
    store.save_cursor(cursor)

    draft = store.load_current_draft()
    if draft and draft.approved_for_slot and draft.approved_at:
        now_iso = datetime.now(timezone.utc).isoformat()
        if should_publish_now(
            approved_at_iso=draft.approved_at,
            now_iso=now_iso,
            slot_hour=15,
            slot_minute=0,
        ):
            telegram_api.send_message(config.telegram_channel_id, draft.current_text)
            backlog = store.load_backlog()
            published_ids = set(draft.selected_story_ids)
            published_urls = store.load_published()
            for item in backlog:
                if item.item_id in published_ids:
                    item.status = "published"
                    published_urls.append(item.source_url)
            store.save_backlog(backlog)
            store.save_published(sorted(set(published_urls)))
            draft.status = "published"
            store.save_current_draft(draft)
    elif draft and not draft.approved_for_slot and draft.approved_at:
        telegram_api.send_message(config.telegram_channel_id, draft.current_text)
        backlog = store.load_backlog()
        published_ids = set(draft.selected_story_ids)
        published_urls = store.load_published()
        for item in backlog:
            if item.item_id in published_ids:
                item.status = "published"
                published_urls.append(item.source_url)
        store.save_backlog(backlog)
        store.save_published(sorted(set(published_urls)))
        draft.status = "published"
        store.save_current_draft(draft)
```

- [ ] **Step 5: Run the script test to verify it passes**

Run: `python -m pytest tests/test_scripts.py -q`

Expected: PASS with `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_daily_slot.py scripts/poll_telegram_updates.py tests/test_scripts.py
git commit -m "feat: add daily slot and telegram polling scripts"
```

## Task 7: Add GitHub Actions workflows, state commits, and operator documentation

**Files:**
- Create: `.github/workflows/daily_slot.yml`
- Create: `.github/workflows/poll_telegram.yml`
- Create: `README.md`

- [ ] **Step 1: Write the operator README**

```markdown
# AI News Telegram Bot

## Required secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_CHAT_ID`
- `TELEGRAM_CHANNEL_ID`

## Local commands

- `python -m pytest -q`
- `python scripts/run_daily_slot.py`
- `python scripts/poll_telegram_updates.py`

## Telegram owner commands

- `/backlog`
- `/short <item_id>`
- `/publish_now <item_id>`
- `Edit` button then replacement text message
- `Approve for 18:00` button
- `Publish now` button
```

- [ ] **Step 2: Add the daily slot workflow**

```yaml
# .github/workflows/daily_slot.yml
name: daily-slot

on:
  schedule:
    - cron: "30 14 * * *"
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install .[dev]
      - run: python scripts/run_daily_slot.py
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_OWNER_CHAT_ID: ${{ secrets.TELEGRAM_OWNER_CHAT_ID }}
          TELEGRAM_CHANNEL_ID: ${{ secrets.TELEGRAM_CHANNEL_ID }}
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add state/
          git diff --cached --quiet || git commit -m "chore: update bot state after daily slot"
          git push
```

- [ ] **Step 3: Add the polling workflow**

```yaml
# .github/workflows/poll_telegram.yml
name: poll-telegram

on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install .[dev]
      - run: python scripts/poll_telegram_updates.py
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_OWNER_CHAT_ID: ${{ secrets.TELEGRAM_OWNER_CHAT_ID }}
          TELEGRAM_CHANNEL_ID: ${{ secrets.TELEGRAM_CHANNEL_ID }}
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add state/
          git diff --cached --quiet || git commit -m "chore: update bot state after telegram poll"
          git push
```

- [ ] **Step 4: Run the full test suite**

Run: `python -m pytest -q`

Expected: PASS with all tests green.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily_slot.yml .github/workflows/poll_telegram.yml README.md
git commit -m "chore: add github actions workflows and operator docs"
```

## Self-Review

### Spec coverage

- Backlog accumulation: covered in Task 2 and Task 3.
- Daily 18:00 editorial slot: covered in Task 1 config defaults, Task 5 timing logic, and Task 7 workflow scheduling.
- Draft or short-post modes: covered in Task 4 and Task 6.
- Draft delivery to owner in private Telegram chat: covered in Task 6.
- Draft editing before publish: covered in Task 5 and Task 6.
- Manual approval before publish: covered in Task 5 and Task 6.
- Separate delayed and immediate publish actions: covered in Task 5 and Task 6.
- Actual publish to the channel after approval: covered in Task 6.
- Unpublished items remain available until stale: covered in Task 3 backlog merge/expiry rules.
- No-cost architecture: covered by raw Telegram API, JSON repo state, and GitHub Actions workflows in Task 7.

### Placeholder scan

- No `TBD`, `TODO`, or empty implementation steps remain.
- Every code-changing step includes exact file content or concrete snippets.
- Every verification step includes an explicit command and expected result.

### Type consistency

- `BacklogItem`, `DraftRecord`, `JsonStateStore`, `build_main_slot_draft`, `should_publish_now`, and command names are consistent across tasks.
- Draft status values remain `pending`, `editing`, `published`, `skipped`, `failed`.
- Backlog status values remain `new`, `queued`, `drafted`, `published`, `skipped`, `expired`.

## Notes for Execution

- Keep the first version deliberately simple: do not add embeddings, vector search, LLM APIs, or a database.
- If translation quality is unacceptable in manual testing, swap the `drafts.py` translation function behind the same interface instead of redesigning the pipeline.
- If Google News RSS proves too noisy, refine `AI_SEARCH_QUERIES` and ranking weights before introducing new infrastructure.
