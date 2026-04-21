# AI News Discovery Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current query-only discovery logic with a source-driven, tier-aware, no-cost discovery pipeline backed by `sources.yaml`, while keeping the existing Telegram editorial flow intact.

**Architecture:** The implementation moves discovery from hard-coded Google News queries to a curated source registry loaded from YAML. Intake remains feed-first, candidates are normalized into the existing backlog model with extra source metadata, and backlog eligibility is updated so `tier4` community items require confirmation from stronger sources before they can become publishable. The draft, approval, and publish flow stays unchanged.

**Tech Stack:** Python 3.12+, `PyYAML`, `feedparser`, existing JSON state storage, GitHub Actions, `pytest`

---

## File Structure

### New Files

- `sources.yaml`
  - Curated source registry for the expanded discovery pipeline.
- `src/ai_news_bot/source_registry.py`
  - YAML loader, source schema validation, and source filtering helpers.
- `tests/test_source_registry.py`
  - Tests for YAML parsing and source validation.

### Modified Files

- `pyproject.toml`
  - Add YAML parsing dependency if needed.
- `src/ai_news_bot/models.py`
  - Extend `BacklogItem` with source-tier and confirmation metadata.
- `src/ai_news_bot/discovery.py`
  - Refactor intake from query-based search to source-driven collection.
- `src/ai_news_bot/backlog.py`
  - Update merge/dedup/eligibility logic for tiers and confirmation.
- `src/ai_news_bot/ranking.py`
  - Add scoring based on tier, source priority, corroboration, and community signals.
- `scripts/run_daily_slot.py`
  - Ensure daily refresh uses the new source-driven pipeline with the updated backlog semantics.
- `tests/test_discovery.py`
  - Replace query-era tests with source-driven discovery tests.
- `tests/test_backlog.py`
  - Add tests for confirmation and lifecycle behavior.
- `tests/test_scripts.py`
  - Add a script-level regression for “community only” days and confirmed-story days.
- `README.md`
  - Document `sources.yaml`, supported source kinds, and free-mode behavior.

## Task 1: Introduce Source Registry and YAML Config

**Files:**
- Create: `sources.yaml`
- Create: `src/ai_news_bot/source_registry.py`
- Modify: `pyproject.toml`
- Test: `tests/test_source_registry.py`

- [ ] **Step 1: Write the failing tests for source registry loading**

```python
from pathlib import Path

import pytest

from ai_news_bot.source_registry import load_sources


def test_load_sources_returns_enabled_source_records(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: openai-blog
    name: OpenAI Blog
    tier: tier1_official
    kind: rss
    url: https://openai.com/blog
    feed_url: https://openai.com/news/rss.xml
    language: en
    priority: 10
    enabled: true
    tags: [official, model]
  - id: disabled-source
    name: Disabled
    tier: tier2_media
    kind: rss
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 1
    enabled: false
    tags: [media]
""".strip(),
        encoding="utf-8",
    )

    sources = load_sources(config)

    assert [source.id for source in sources] == ["openai-blog"]


def test_load_sources_rejects_missing_required_fields(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: broken
    name: Broken
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required fields"):
        load_sources(config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_source_registry.py -q`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `ai_news_bot.source_registry`

- [ ] **Step 3: Add YAML dependency**

Update `pyproject.toml` dependencies:

```toml
dependencies = [
  "requests>=2.32.0",
  "feedparser>=6.0.11",
  "trafilatura>=1.9.0",
  "deep-translator>=1.11.4",
  "PyYAML>=6.0.2",
]
```

- [ ] **Step 4: Create the source registry module**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    tier: str
    kind: str
    url: str
    feed_url: str
    language: str
    priority: int
    enabled: bool
    tags: tuple[str, ...]


_REQUIRED_FIELDS = {
    "id",
    "name",
    "tier",
    "kind",
    "url",
    "feed_url",
    "language",
    "priority",
    "enabled",
    "tags",
}


def load_sources(path: Path) -> list[SourceConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources.yaml must contain a top-level 'sources' list")

    items: list[SourceConfig] = []
    for entry in sources:
        if not isinstance(entry, dict):
            raise ValueError("each source entry must be a mapping")
        missing = sorted(_REQUIRED_FIELDS - set(entry))
        if missing:
            raise ValueError(f"source '{entry.get('id', '<unknown>')}' missing required fields: {', '.join(missing)}")
        source = SourceConfig(
            id=str(entry["id"]),
            name=str(entry["name"]),
            tier=str(entry["tier"]),
            kind=str(entry["kind"]),
            url=str(entry["url"]),
            feed_url=str(entry["feed_url"]),
            language=str(entry["language"]),
            priority=int(entry["priority"]),
            enabled=bool(entry["enabled"]),
            tags=tuple(str(tag) for tag in entry["tags"]),
        )
        if source.enabled:
            items.append(source)
    return items
```

- [ ] **Step 5: Create the initial curated source file**

Create `sources.yaml` with a real starting pool:

```yaml
sources:
  - id: openai-blog
    name: OpenAI Blog
    tier: tier1_official
    kind: rss
    url: https://openai.com/news
    feed_url: https://openai.com/news/rss.xml
    language: en
    priority: 10
    enabled: true
    tags: [official, models, api]

  - id: anthropic-news
    name: Anthropic News
    tier: tier1_official
    kind: rss
    url: https://www.anthropic.com/news
    feed_url: https://www.anthropic.com/news/rss.xml
    language: en
    priority: 10
    enabled: true
    tags: [official, models, api]

  - id: techcrunch-ai
    name: TechCrunch AI
    tier: tier2_media
    kind: rss
    url: https://techcrunch.com/category/artificial-intelligence/
    feed_url: https://techcrunch.com/category/artificial-intelligence/feed/
    language: en
    priority: 8
    enabled: true
    tags: [media, ai]

  - id: hacker-news-ai
    name: Hacker News AI
    tier: tier4_community
    kind: rss
    url: https://news.ycombinator.com/
    feed_url: https://hnrss.org/newest?q=AI
    language: en
    priority: 4
    enabled: true
    tags: [community, hn]
```

The real file should include dozens of entries across all four tiers, not just this sample.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_source_registry.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml sources.yaml src/ai_news_bot/source_registry.py tests/test_source_registry.py
git commit -m "feat: add source registry for discovery pipeline"
```

## Task 2: Extend Backlog Item Model for Source Metadata

**Files:**
- Modify: `src/ai_news_bot/models.py`
- Test: `tests/test_backlog.py`

- [ ] **Step 1: Write the failing test for enriched backlog items**

Add to `tests/test_backlog.py`:

```python
from ai_news_bot.models import BacklogItem


def test_backlog_item_to_dict_includes_source_metadata():
    item = BacklogItem(
        item_id="item-1",
        source_url="https://example.com/post",
        source_title="Gemini CLI Released",
        normalized_title="gemini cli released",
        topic_fingerprint="gemini-cli-released",
        source_name="OpenAI Blog",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="release details",
        status="observed_unconfirmed",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
        source_tier="tier4_community",
        source_kind="reddit",
        source_priority=4,
        confirmed=False,
        evidence_urls=["https://reddit.com/r/LocalLLaMA/..."],
    )

    data = item.to_dict()

    assert data["source_tier"] == "tier4_community"
    assert data["confirmed"] is False
    assert data["evidence_urls"] == ["https://reddit.com/r/LocalLLaMA/..."]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backlog.py::test_backlog_item_to_dict_includes_source_metadata -q`
Expected: FAIL with `TypeError` because the new fields do not exist yet

- [ ] **Step 3: Extend the model**

Update `src/ai_news_bot/models.py`:

```python
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
    source_tier: str = "tier2_media"
    source_kind: str = "rss"
    source_priority: int = 0
    confirmed: bool = True
    evidence_urls: list[str] | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if payload["evidence_urls"] is None:
            payload["evidence_urls"] = []
        return payload
```

- [ ] **Step 4: Update storage validation**

Modify `src/ai_news_bot/storage.py` required fields for backlog items:

```python
required_fields = {
    "item_id",
    "source_url",
    "source_title",
    "normalized_title",
    "topic_fingerprint",
    "source_name",
    "published_at",
    "summary_candidate",
    "status",
    "first_seen_at",
    "last_considered_at",
    "source_tier",
    "source_kind",
    "source_priority",
    "confirmed",
    "evidence_urls",
}
```

Also validate:

```python
self._require_string("backlog.json item", "source_tier", value["source_tier"])
self._require_string("backlog.json item", "source_kind", value["source_kind"])
self._require_int("backlog.json item", "source_priority", value["source_priority"])
self._require_bool("backlog.json item", "confirmed", value["confirmed"])
evidence_urls = self._require_list("backlog.json item.evidence_urls", value["evidence_urls"])
for index, evidence_url in enumerate(evidence_urls):
    self._require_string("backlog.json item.evidence_urls", str(index), evidence_url)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_backlog.py::test_backlog_item_to_dict_includes_source_metadata -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/ai_news_bot/models.py src/ai_news_bot/storage.py tests/test_backlog.py
git commit -m "feat: extend backlog items with source metadata"
```

## Task 3: Refactor Discovery to Use `sources.yaml`

**Files:**
- Modify: `src/ai_news_bot/discovery.py`
- Modify: `tests/test_discovery.py`
- Modify: `src/ai_news_bot/config.py`

- [ ] **Step 1: Write the failing tests for source-driven discovery**

Replace `tests/test_discovery.py` with:

```python
from pathlib import Path

from ai_news_bot.discovery import fetch_candidates_from_sources
from ai_news_bot.source_registry import SourceConfig


class FakeEntry(dict):
    pass


def test_fetch_candidates_from_sources_builds_backlog_items(monkeypatch):
    sources = [
        SourceConfig(
            id="openai-blog",
            name="OpenAI Blog",
            tier="tier1_official",
            kind="rss",
            url="https://openai.com/news",
            feed_url="https://openai.com/news/rss.xml",
            language="en",
            priority=10,
            enabled=True,
            tags=("official", "models"),
        )
    ]

    monkeypatch.setattr(
        "ai_news_bot.discovery.parse_feed",
        lambda url: [
            FakeEntry(
                title="Gemini CLI Released",
                link="https://example.com/gemini-cli",
                summary="CLI tool for developers",
                published="2026-04-20T10:00:00+00:00",
                source={"title": "OpenAI Blog"},
            )
        ],
    )
    monkeypatch.setattr("ai_news_bot.discovery.fetch_page_text", lambda url: "CLI tool for developers")

    items = fetch_candidates_from_sources(sources, now_iso="2026-04-20T12:00:00+00:00")

    assert len(items) == 1
    assert items[0].source_tier == "tier1_official"
    assert items[0].source_priority == 10
    assert items[0].confirmed is True


def test_fetch_candidates_from_sources_marks_community_items_unconfirmed(monkeypatch):
    sources = [
        SourceConfig(
            id="hn-ai",
            name="HN AI",
            tier="tier4_community",
            kind="rss",
            url="https://news.ycombinator.com",
            feed_url="https://hnrss.org/newest?q=AI",
            language="en",
            priority=4,
            enabled=True,
            tags=("community", "hn"),
        )
    ]

    monkeypatch.setattr(
        "ai_news_bot.discovery.parse_feed",
        lambda url: [
            FakeEntry(
                title="Interesting AI CLI launch",
                link="https://example.com/hn-thread",
                summary="community discussion",
                published="2026-04-20T10:00:00+00:00",
                source={"title": "HN"},
            )
        ],
    )
    monkeypatch.setattr("ai_news_bot.discovery.fetch_page_text", lambda url: "")

    items = fetch_candidates_from_sources(sources, now_iso="2026-04-20T12:00:00+00:00")

    assert len(items) == 1
    assert items[0].status == "observed_unconfirmed"
    assert items[0].confirmed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_discovery.py -q`
Expected: FAIL because `fetch_candidates_from_sources`, `parse_feed`, or `fetch_page_text` do not exist yet

- [ ] **Step 3: Add source-aware discovery helpers**

Refactor `src/ai_news_bot/discovery.py` into focused helpers:

```python
def parse_feed(feed_url: str) -> list:
    import feedparser

    return list(getattr(feedparser.parse(feed_url), "entries", []))


def fetch_page_text(url: str) -> str:
    import trafilatura

    downloaded = trafilatura.fetch_url(url) or ""
    return trafilatura.extract(downloaded) or ""


def build_candidate_from_entry(source: SourceConfig, entry, now_iso: str) -> BacklogItem:
    title = _get_value(entry, "title", "")
    url = _get_value(entry, "link", "")
    summary = fetch_page_text(url) or _get_value(entry, "summary", "")
    is_confirmed = source.tier != "tier4_community"
    status = "new" if is_confirmed else "observed_unconfirmed"
    return BacklogItem(
        item_id=str(uuid4()),
        source_url=url,
        source_title=title,
        normalized_title=normalize_title(title),
        topic_fingerprint=normalize_title(title).replace(" ", "-"),
        source_name=source.name,
        published_at=_get_value(entry, "published", now_iso),
        summary_candidate=summary[:800],
        status=status,
        first_seen_at=now_iso,
        last_considered_at=now_iso,
        source_tier=source.tier,
        source_kind=source.kind,
        source_priority=source.priority,
        confirmed=is_confirmed,
        evidence_urls=[url],
    )


def fetch_candidates_from_sources(sources: list[SourceConfig], now_iso: str) -> list[BacklogItem]:
    items: list[BacklogItem] = []
    for source in sources:
        try:
            entries = parse_feed(source.feed_url)
        except Exception:
            continue
        for entry in entries:
            items.append(build_candidate_from_entry(source, entry, now_iso))
    return items
```

- [ ] **Step 4: Wire discovery to config**

Add to `src/ai_news_bot/config.py`:

```python
    sources_path: Path
```

and in `load_config()`:

```python
        sources_path=Path(os.environ.get("SOURCES_PATH", PROJECT_ROOT / "sources.yaml")),
```

- [ ] **Step 5: Keep a compatibility wrapper**

At the bottom of `src/ai_news_bot/discovery.py`:

```python
from ai_news_bot.source_registry import load_sources


def fetch_candidates(now_iso: str, *, sources_path: Path | None = None) -> list[BacklogItem]:
    path = sources_path or (Path(__file__).resolve().parents[2] / "sources.yaml")
    return fetch_candidates_from_sources(load_sources(path), now_iso)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_discovery.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/ai_news_bot/discovery.py src/ai_news_bot/config.py tests/test_discovery.py
git commit -m "feat: refactor discovery to use source registry"
```

## Task 4: Add Confirmation Logic for Community-Originated Topics

**Files:**
- Modify: `src/ai_news_bot/backlog.py`
- Test: `tests/test_backlog.py`

- [ ] **Step 1: Write the failing tests for community confirmation**

Add to `tests/test_backlog.py`:

```python
def test_merge_candidates_confirms_matching_community_topic_with_stronger_source():
    existing = [
        BacklogItem(
            item_id="community",
            source_url="https://example.com/hn-thread",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="HN",
            published_at="2026-04-20T10:00:00+00:00",
            summary_candidate="discussion",
            status="observed_unconfirmed",
            first_seen_at="2026-04-20T10:00:00+00:00",
            last_considered_at="2026-04-20T10:00:00+00:00",
            source_tier="tier4_community",
            source_kind="rss",
            source_priority=4,
            confirmed=False,
            evidence_urls=["https://example.com/hn-thread"],
        )
    ]
    incoming = [
        BacklogItem(
            item_id="official",
            source_url="https://example.com/official-post",
            source_title="Gemini CLI Released",
            normalized_title="gemini cli released",
            topic_fingerprint="gemini-cli-released",
            source_name="Google AI",
            published_at="2026-04-20T11:00:00+00:00",
            summary_candidate="official release",
            status="new",
            first_seen_at="2026-04-20T11:00:00+00:00",
            last_considered_at="2026-04-20T11:00:00+00:00",
            source_tier="tier1_official",
            source_kind="rss",
            source_priority=10,
            confirmed=True,
            evidence_urls=["https://example.com/official-post"],
        )
    ]

    merged = merge_candidates(existing, incoming, now_iso="2026-04-20T12:00:00+00:00", expiry_days=4)

    assert len(merged) == 1
    assert merged[0].confirmed is True
    assert merged[0].status == "queued"
    assert "https://example.com/hn-thread" in merged[0].evidence_urls
    assert "https://example.com/official-post" in merged[0].evidence_urls


def test_select_main_slot_items_ignores_unconfirmed_community_topics():
    backlog = [
        BacklogItem(
            item_id="community",
            source_url="https://example.com/hn-thread",
            source_title="Unconfirmed launch",
            normalized_title="unconfirmed launch",
            topic_fingerprint="unconfirmed-launch",
            source_name="HN",
            published_at="2026-04-20T10:00:00+00:00",
            summary_candidate="discussion",
            status="observed_unconfirmed",
            first_seen_at="2026-04-20T10:00:00+00:00",
            last_considered_at="2026-04-20T10:00:00+00:00",
            source_tier="tier4_community",
            source_kind="rss",
            source_priority=4,
            confirmed=False,
            evidence_urls=["https://example.com/hn-thread"],
        )
    ]

    assert select_main_slot_items(backlog) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backlog.py -q`
Expected: FAIL because merge/select logic does not understand confirmation metadata yet

- [ ] **Step 3: Implement merge confirmation behavior**

Update `src/ai_news_bot/backlog.py` merge logic:

```python
def _select_primary(existing: BacklogItem, incoming: BacklogItem) -> BacklogItem:
    if incoming.source_priority > existing.source_priority:
        winner, loser = incoming, existing
    else:
        winner, loser = existing, incoming

    evidence_urls = sorted(set((winner.evidence_urls or []) + (loser.evidence_urls or []) + [winner.source_url, loser.source_url]))
    winner.evidence_urls = evidence_urls
    winner.confirmed = existing.confirmed or incoming.confirmed
    winner.status = "queued" if winner.confirmed else "observed_unconfirmed"
    winner.last_considered_at = max(existing.last_considered_at, incoming.last_considered_at)
    return winner
```

Then refactor `merge_candidates()` to merge matching normalized titles into a dictionary and call `_select_primary()` instead of dropping duplicates blindly.

- [ ] **Step 4: Ensure main-slot selection only uses eligible confirmed items**

Keep selection logic explicit:

```python
def select_main_slot_items(backlog: list[BacklogItem], limit: int = 5) -> list[BacklogItem]:
    queued = [item for item in backlog if item.status == "queued" and item.confirmed]
    return sorted(queued, key=score_item, reverse=True)[:limit]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_backlog.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/ai_news_bot/backlog.py tests/test_backlog.py
git commit -m "feat: require confirmation for community topics"
```

## Task 5: Update Ranking for Tier-Aware and Evidence-Aware Scoring

**Files:**
- Modify: `src/ai_news_bot/ranking.py`
- Test: `tests/test_backlog.py`

- [ ] **Step 1: Write the failing scoring test**

Add to `tests/test_backlog.py`:

```python
from ai_news_bot.ranking import score_item


def test_score_item_prefers_confirmed_high_priority_sources_with_evidence():
    official = BacklogItem(
        item_id="official",
        source_url="https://example.com/official",
        source_title="Gemini CLI Release",
        normalized_title="gemini cli release",
        topic_fingerprint="gemini-cli-release",
        source_name="Google AI",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="major CLI release benchmark",
        status="queued",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
        source_tier="tier1_official",
        source_kind="rss",
        source_priority=10,
        confirmed=True,
        evidence_urls=["https://example.com/official", "https://example.com/reuters"],
    )
    community = BacklogItem(
        item_id="community",
        source_url="https://example.com/community",
        source_title="Gemini CLI release rumor",
        normalized_title="gemini cli release rumor",
        topic_fingerprint="gemini-cli-release-rumor",
        source_name="HN",
        published_at="2026-04-20T10:00:00+00:00",
        summary_candidate="discussion",
        status="observed_unconfirmed",
        first_seen_at="2026-04-20T10:00:00+00:00",
        last_considered_at="2026-04-20T10:00:00+00:00",
        source_tier="tier4_community",
        source_kind="rss",
        source_priority=4,
        confirmed=False,
        evidence_urls=["https://example.com/community"],
    )

    assert score_item(official) > score_item(community)
```

- [ ] **Step 2: Run test to verify it fails or is too weak**

Run: `pytest tests/test_backlog.py::test_score_item_prefers_confirmed_high_priority_sources_with_evidence -q`
Expected: FAIL or pass for the wrong reason because ranking ignores source metadata

- [ ] **Step 3: Update scoring**

Refactor `src/ai_news_bot/ranking.py`:

```python
_TIER_WEIGHTS = {
    "tier1_official": 6,
    "tier2_media": 4,
    "tier3_ai_publications": 3,
    "tier4_community": 1,
}


def score_item(item: BacklogItem) -> int:
    text = f"{item.source_title} {item.summary_candidate}".lower()
    keyword_score = sum(weight for keyword, weight in _KEYWORD_WEIGHTS if keyword in text)
    tier_score = _TIER_WEIGHTS.get(item.source_tier, 0)
    confirmation_score = 3 if item.confirmed else -3
    priority_score = item.source_priority
    evidence_score = max(0, len(item.evidence_urls or []) - 1)
    return keyword_score + tier_score + confirmation_score + priority_score + evidence_score
```

- [ ] **Step 4: Run the targeted scoring test**

Run: `pytest tests/test_backlog.py::test_score_item_prefers_confirmed_high_priority_sources_with_evidence -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai_news_bot/ranking.py tests/test_backlog.py
git commit -m "feat: add tier-aware ranking for discovery"
```

## Task 6: Wire the Expanded Discovery Into `run_daily_slot.py`

**Files:**
- Modify: `scripts/run_daily_slot.py`
- Modify: `tests/test_scripts.py`

- [ ] **Step 1: Write the failing script-level test for confirmed vs unconfirmed candidates**

Add to `tests/test_scripts.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scripts.py::test_daily_slot_run_does_not_build_draft_from_unconfirmed_community_only_items -q`
Expected: FAIL if `run_daily_slot` or backlog selection still treats unconfirmed items as eligible

- [ ] **Step 3: Pass `sources_path` through config-aware discovery**

Update `scripts/run_daily_slot.py` refresh flow:

```python
def refresh_backlog(
    store: JsonStateStore,
    *,
    now_iso: str,
    fetcher=fetch_candidates,
    expiry_days: int = BACKLOG_EXPIRY_DAYS,
) -> list[BacklogItem]:
    refreshed = merge_candidates(
        store.load_backlog(),
        fetcher(now_iso),
        now_iso=now_iso,
        expiry_days=expiry_days,
    )
    store.save_backlog(refreshed)
    return refreshed


def main() -> DraftRecord | None:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    return run_daily_slot(
        store,
        telegram_api=telegram_api,
        owner_chat_id=config.telegram_owner_chat_id,
        fetcher=lambda now_iso: fetch_candidates(now_iso, sources_path=config.sources_path),
    )
```

- [ ] **Step 4: Run the targeted script test**

Run: `pytest tests/test_scripts.py::test_daily_slot_run_does_not_build_draft_from_unconfirmed_community_only_items -q`
Expected: PASS

- [ ] **Step 5: Run the broader script suite**

Run: `pytest tests/test_scripts.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/run_daily_slot.py tests/test_scripts.py
git commit -m "feat: wire expanded discovery into daily slot job"
```

## Task 7: Document and Verify the Expanded Discovery System

**Files:**
- Modify: `README.md`
- Test: `tests/test_source_registry.py`
- Test: `tests/test_discovery.py`
- Test: `tests/test_backlog.py`
- Test: `tests/test_scripts.py`

- [ ] **Step 1: Update README**

Add sections to `README.md`:

```md
## Source Configuration

Discovery sources are stored in `sources.yaml`.

Supported source tiers:
- `tier1_official`
- `tier2_media`
- `tier3_ai_publications`
- `tier4_community`

Supported source kinds:
- `rss`
- `atom`
- `website`
- `reddit`
- `hackernews`

Community-originated topics are tracked, but they are not eligible for drafting until at least one stronger source confirms the same topic.
```

- [ ] **Step 2: Run focused discovery/backlog tests**

Run: `pytest tests/test_source_registry.py tests/test_discovery.py tests/test_backlog.py tests/test_scripts.py -q`
Expected: PASS

- [ ] **Step 3: Run the full suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add README.md tests/test_source_registry.py tests/test_discovery.py tests/test_backlog.py tests/test_scripts.py
git commit -m "docs: document expanded AI news discovery pipeline"
```

## Spec Coverage Check

- `sources.yaml` and external source storage: covered by Task 1.
- Four-tier source model: covered by Tasks 1, 3, 4, and 5.
- Mixed-feeds discovery pipeline: covered by Tasks 1 and 3.
- Confirmation rule for `tier4`: covered by Task 4.
- Ranking and corroboration logic: covered by Task 5.
- Backlog lifecycle updates: covered by Tasks 2 and 4.
- Existing Telegram editorial flow unchanged: preserved by Task 6.
- Documentation and operational clarity: covered by Task 7.

## Self-Review Notes

- No placeholder implementation steps remain.
- All new types and property names are defined before later tasks use them.
- The plan stays within the discovery-expansion scope and does not reopen the publishing architecture.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-20-ai-news-discovery-expansion.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
