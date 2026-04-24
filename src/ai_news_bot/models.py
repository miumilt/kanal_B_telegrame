from __future__ import annotations

from dataclasses import asdict, dataclass, field


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
    evidence_urls: list[str] = field(default_factory=list)
    category: str = "major_news"
    image_url: str | None = None
    video_url: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if payload["evidence_urls"] is None:
            payload["evidence_urls"] = []
        return payload


@dataclass
class DraftRecord:
    draft_id: str
    generated_text: str
    current_text: str
    selected_story_ids: list[str]
    draft_type: str
    status: str
    created_at: str
    category: str = ""
    header_label: str = ""
    image_url: str | None = None
    video_url: str | None = None
    publication_state: str = "finalize_only"

    def to_dict(self) -> dict:
        return asdict(self)
