from __future__ import annotations

from ai_news_bot.models import DraftRecord


def build_draft_keyboard(draft_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Edit", "callback_data": f"edit:{draft_id}"},
                {"text": "Publish now", "callback_data": f"publish_now:{draft_id}"},
                {"text": "Skip", "callback_data": f"skip:{draft_id}"},
            ]
        ]
    }


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
