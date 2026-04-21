from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

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

_VALID_TIERS = {
    "tier1_official",
    "tier2_media",
    "tier3_ai_publications",
    "tier4_community",
}

_VALID_KINDS = {
    "rss",
    "atom",
    "website",
    "reddit",
    "hackernews",
}


def load_sources(path: Path) -> list[SourceConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("sources.yaml must contain a top-level mapping")
    if "sources" not in raw:
        raise ValueError("sources.yaml must contain a top-level 'sources' key")
    sources = raw["sources"]
    if not isinstance(sources, list):
        raise ValueError("sources.yaml must contain a top-level 'sources' list")

    loaded: list[SourceConfig] = []
    seen_ids: set[str] = set()
    for entry in sources:
        if not isinstance(entry, dict):
            raise ValueError("each source entry must be a mapping")

        missing = sorted(_REQUIRED_FIELDS - set(entry))
        if missing:
            source_id = entry.get("id", "<unknown>")
            missing_fields = ", ".join(missing)
            raise ValueError(f"source '{source_id}' missing required fields: {missing_fields}")

        source = SourceConfig(
            id=_require_string(entry["id"], "id"),
            name=_require_string(entry["name"], "name"),
            tier=_require_choice(entry["tier"], "tier", _VALID_TIERS),
            kind=_require_choice(entry["kind"], "kind", _VALID_KINDS),
            url=_require_http_url(entry["url"], "url"),
            feed_url=_require_http_url(entry["feed_url"], "feed_url"),
            language=_require_string(entry["language"], "language"),
            priority=_require_int(entry["priority"], "priority"),
            enabled=_require_bool(entry["enabled"], "enabled"),
            tags=_require_tags(entry["tags"]),
        )
        if source.id in seen_ids:
            raise ValueError(f"duplicate source id '{source.id}'")
        seen_ids.add(source.id)
        if source.enabled:
            loaded.append(source)

    return loaded


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"source field '{field}' must be an integer")
    return value


def _require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"source field '{field}' must be a boolean")
    return value


def _require_tags(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("source field 'tags' must be a list")
    tags: list[str] = []
    for tag in value:
        if not isinstance(tag, str):
            raise ValueError("source field 'tags' must be a list of strings")
        tags.append(tag)
    return tuple(tags)


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"source field '{field}' must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"source field '{field}' must not be blank")
    return value


def _require_choice(value: object, field: str, allowed: set[str]) -> str:
    value = _require_string(value, field)
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"source field '{field}' must be one of: {allowed_values}")
    return value


def _require_http_url(value: object, field: str) -> str:
    value = _require_string(value, field)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"source field '{field}' must be a http(s) URL")
    return value
