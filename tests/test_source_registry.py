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


def test_load_sources_rejects_missing_top_level_sources_key(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
not_sources: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="top-level 'sources' key"):
        load_sources(config)


def test_load_sources_rejects_non_string_fields(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: broken
    name: 123
    tier: tier1_official
    kind: rss
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source field 'name' must be a string"):
        load_sources(config)


def test_load_sources_rejects_non_string_tags(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: broken
    name: Broken
    tier: tier1_official
    kind: rss
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official, 123]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tags' must be a list of strings"):
        load_sources(config)


def test_load_sources_rejects_duplicate_ids(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: duplicate
    name: First
    tier: tier1_official
    kind: rss
    url: https://example.com/first
    feed_url: https://example.com/first.rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
  - id: duplicate
    name: Second
    tier: tier2_media
    kind: rss
    url: https://example.com/second
    feed_url: https://example.com/second.rss
    language: en
    priority: 5
    enabled: true
    tags: [media]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate source id 'duplicate'"):
        load_sources(config)


def test_load_sources_rejects_blank_required_string_fields(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: blank-id
    name: " "
    tier: tier1_official
    kind: rss
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source field 'name' must not be blank"):
        load_sources(config)


def test_load_sources_rejects_invalid_tier(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: bad-tier
    name: Bad Tier
    tier: tier0_unknown
    kind: rss
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source field 'tier' must be one of"):
        load_sources(config)


def test_load_sources_rejects_invalid_kind(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: bad-kind
    name: Bad Kind
    tier: tier1_official
    kind: xml
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source field 'kind' must be one of"):
        load_sources(config)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("url", '"   "', "must not be blank"),
        ("feed_url", "ftp://example.com/rss", "must be a http(s) URL"),
    ],
)
def test_load_sources_rejects_invalid_urls(tmp_path: Path, field_name: str, value: str, message: str):
    config = tmp_path / "sources.yaml"
    config.write_text(
        f"""
sources:
  - id: bad-{field_name}
    name: Bad {field_name}
    tier: tier1_official
    kind: rss
    url: {"https://example.com" if field_name == "feed_url" else value}
    feed_url: {"https://example.com/rss" if field_name == "url" else value}
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    pattern = (
        rf"source field '{field_name}' must not be blank"
        if message == "must not be blank"
        else rf"source field '{field_name}' must be a http\(s\) URL"
    )
    with pytest.raises(ValueError, match=pattern):
        load_sources(config)


def test_load_sources_rejects_url_with_missing_host(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: missing-host
    name: Missing Host
    tier: tier1_official
    kind: rss
    url: https://
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source field 'url' must be a http\\(s\\) URL"):
        load_sources(config)


def test_load_sources_strips_required_strings(tmp_path: Path):
    config = tmp_path / "sources.yaml"
    config.write_text(
        """
sources:
  - id: "  padded-id  "
    name: "  Padded Name  "
    tier: tier1_official
    kind: rss
    url: https://example.com
    feed_url: https://example.com/rss
    language: en
    priority: 10
    enabled: true
    tags: [official]
""".strip(),
        encoding="utf-8",
    )

    sources = load_sources(config)

    assert sources[0].id == "padded-id"
    assert sources[0].name == "Padded Name"
