from __future__ import annotations

import json
import os
import tempfile
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
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} contains invalid JSON") from exc

    def _write_json(self, name: str, value) -> None:
        target = self._path(name)
        temp_path = None
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.root,
            prefix=f".{name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            try:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            except Exception:
                handle.close()
                temp_path.unlink(missing_ok=True)
                raise
        try:
            temp_path.replace(target)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _require_dict(self, name: str, value) -> dict:
        if not isinstance(value, dict):
            raise ValueError(f"{name} must contain a JSON object")
        return value

    def _require_list(self, name: str, value) -> list:
        if not isinstance(value, list):
            raise ValueError(f"{name} must contain a JSON array")
        return value

    def _require_fields(self, name: str, value: dict, fields: set[str]) -> None:
        missing = sorted(field for field in fields if field not in value)
        if missing:
            missing_fields = ", ".join(missing)
            raise ValueError(f"{name} is missing required fields: {missing_fields}")

    def _require_only_fields(self, name: str, value: dict, fields: set[str]) -> None:
        unexpected = sorted(field for field in value if field not in fields)
        if unexpected:
            unexpected_fields = ", ".join(unexpected)
            raise ValueError(f"{name} contains unexpected fields: {unexpected_fields}")

    def _require_string(self, name: str, field: str, value) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{name}.{field} must be a string")
        return value

    def _require_bool(self, name: str, field: str, value) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{name}.{field} must be a boolean")
        return value

    def _require_int(self, name: str, field: str, value) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name}.{field} must be an integer")
        return value

    def _backlog_metadata_defaults(self) -> dict:
        return {
            "source_tier": "tier2_media",
            "source_kind": "rss",
            "source_priority": 0,
            "confirmed": True,
            "evidence_urls": [],
            "category": "major_news",
            "image_url": None,
        }

    def _load_backlog_item(self, item: object) -> BacklogItem:
        value = self._require_dict("backlog.json item", item)
        core_fields = {
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
        }
        metadata_fields = {
            "source_tier",
            "source_kind",
            "source_priority",
            "confirmed",
            "evidence_urls",
            "category",
            "image_url",
        }
        allowed_fields = core_fields | metadata_fields
        self._require_fields("backlog.json item", value, core_fields)
        self._require_only_fields("backlog.json item", value, allowed_fields)
        string_fields = {
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
        }
        for field in string_fields:
            self._require_string("backlog.json item", field, value[field])
        normalized = {**self._backlog_metadata_defaults(), **value}
        self._require_string("backlog.json item", "source_tier", normalized["source_tier"])
        self._require_string("backlog.json item", "source_kind", normalized["source_kind"])
        self._require_int("backlog.json item", "source_priority", normalized["source_priority"])
        self._require_bool("backlog.json item", "confirmed", normalized["confirmed"])
        evidence_urls = self._require_list("backlog.json item.evidence_urls", normalized["evidence_urls"])
        for index, evidence_url in enumerate(evidence_urls):
            self._require_string("backlog.json item.evidence_urls", str(index), evidence_url)
        normalized["evidence_urls"] = list(evidence_urls)
        self._require_string("backlog.json item", "category", normalized["category"])
        image_url = normalized["image_url"]
        if image_url is not None:
            self._require_string("backlog.json item", "image_url", image_url)
        return BacklogItem(**normalized)

    def _load_draft_record(self, item: object, *, name: str = "current_draft.json") -> DraftRecord:
        value = self._require_dict(name, item)
        required_fields = {
            "draft_id",
            "generated_text",
            "current_text",
            "selected_story_ids",
            "draft_type",
            "status",
            "created_at",
        }
        optional_fields = {
            "category",
            "header_label",
            "image_url",
            "approved_for_slot",
            "approved_at",
            "publication_state",
        }
        allowed_fields = required_fields | optional_fields
        self._require_fields(name, value, required_fields)
        self._require_only_fields(name, value, allowed_fields)
        string_fields = {
            "draft_id",
            "generated_text",
            "current_text",
            "draft_type",
            "status",
            "created_at",
        }
        for field in string_fields:
            self._require_string(name, field, value[field])
        selected_story_ids = self._require_list(f"{name}.selected_story_ids", value["selected_story_ids"])
        for index, selected_story_id in enumerate(selected_story_ids):
            self._require_string(f"{name}.selected_story_ids", str(index), selected_story_id)
        category = value.get("category")
        if category is None:
            category = value["draft_type"]
        else:
            self._require_string(name, "category", category)
        header_label = value.get("header_label")
        if header_label is None:
            header_label = value["draft_type"].replace("_", " ").title()
        else:
            self._require_string(name, "header_label", header_label)
        image_url = value.get("image_url")
        if image_url is not None:
            self._require_string(name, "image_url", image_url)
        status = value["status"]
        approved_at = value.get("approved_at")
        if approved_at is not None:
            self._require_string(name, "approved_at", approved_at)
        approved_for_slot = value.get("approved_for_slot")
        if approved_for_slot is not None:
            approved_for_slot = self._require_bool(name, "approved_for_slot", approved_for_slot)
        legacy_approval_present = approved_at is not None or approved_for_slot is True
        publication_state = value.get("publication_state")
        if publication_state is None:
            publication_state = "needs_send" if status == "pending" and legacy_approval_present else "finalize_only"
        else:
            self._require_string(name, "publication_state", publication_state)
        if status == "pending" and legacy_approval_present:
            status = "publishing"
        normalized = {
            "draft_id": value["draft_id"],
            "generated_text": value["generated_text"],
            "current_text": value["current_text"],
            "selected_story_ids": list(selected_story_ids),
            "draft_type": value["draft_type"],
            "status": status,
            "created_at": value["created_at"],
            "category": category,
            "header_label": header_label,
            "image_url": image_url,
            "publication_state": publication_state,
        }
        return DraftRecord(**normalized)

    def load_backlog(self) -> list[BacklogItem]:
        raw = self._read_json("backlog.json", [])
        items = self._require_list("backlog.json", raw)
        return [self._load_backlog_item(item) for item in items]

    def save_backlog(self, items: list[BacklogItem]) -> None:
        self._write_json("backlog.json", [item.to_dict() for item in items])

    def load_current_draft(self) -> DraftRecord | None:
        raw = self._read_json("current_draft.json", None)
        if raw is None:
            return None
        return self._load_draft_record(raw, name="current_draft.json")

    def save_current_draft(self, draft: DraftRecord | None) -> None:
        payload = None if draft is None else draft.to_dict()
        self._write_json("current_draft.json", payload)

    def load_owner_drafts(self) -> list[DraftRecord]:
        raw = self._read_json("owner_drafts.json", [])
        items = self._require_list("owner_drafts.json", raw)
        return [self._load_draft_record(item, name="owner_drafts.json item") for item in items]

    def save_owner_drafts(self, drafts: list[DraftRecord]) -> None:
        self._write_json("owner_drafts.json", [draft.to_dict() for draft in drafts])

    def load_cursor(self) -> int:
        raw = self._read_json("telegram_cursor.json", {"last_update_id": 0})
        value = self._require_dict("telegram_cursor.json", raw)
        self._require_fields("telegram_cursor.json", value, {"last_update_id"})
        return self._require_int("telegram_cursor.json", "last_update_id", value["last_update_id"])

    def save_cursor(self, update_id: int) -> None:
        self._require_int("telegram_cursor.json", "last_update_id", update_id)
        self._write_json("telegram_cursor.json", {"last_update_id": update_id})

    def load_published(self) -> list[str]:
        raw = self._read_json("published.json", [])
        items = self._require_list("published.json", raw)
        for index, item in enumerate(items):
            self._require_string("published.json", str(index), item)
        return items

    def save_published(self, source_urls: list[str]) -> None:
        for index, source_url in enumerate(source_urls):
            self._require_string("published.json", str(index), source_url)
        self._write_json("published.json", source_urls)
