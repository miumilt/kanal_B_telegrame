from __future__ import annotations

from datetime import datetime, timedelta

from ai_news_bot.models import DraftRecord


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

    eligible_slot = approved_at.replace(
        hour=slot_hour,
        minute=slot_minute,
        second=0,
        microsecond=0,
    )
    if approved_at > eligible_slot:
        eligible_slot += timedelta(days=1)

    return now >= eligible_slot


def mark_draft_approved(draft: DraftRecord, approved_at_iso: str) -> DraftRecord:
    draft.approved_for_slot = True
    draft.approved_at = approved_at_iso
    return draft


def mark_draft_publish_now(draft: DraftRecord, approved_at_iso: str) -> DraftRecord:
    draft.approved_for_slot = False
    draft.approved_at = approved_at_iso
    return draft


def mark_draft_editing(draft: DraftRecord) -> DraftRecord:
    draft.status = "editing"
    return draft


def parse_owner_command(text: str) -> tuple[str, str | None]:
    stripped = text.strip()
    parts = stripped.split(maxsplit=1)
    command = parts[0] if parts else ""

    if command == "/backlog":
        return ("backlog", None)

    if command == "/short" and len(parts) == 2:
        return ("short", parts[1])

    if command == "/publish_now" and len(parts) == 2:
        return ("publish_now", parts[1])

    return ("unknown", None)
