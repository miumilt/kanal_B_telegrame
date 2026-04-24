from __future__ import annotations

from datetime import UTC, datetime

from ai_news_bot.approval import (
    build_draft_keyboard,
    mark_draft_editing,
    parse_owner_command,
)
from ai_news_bot.config import load_config
from ai_news_bot.drafts import build_short_post_text
from ai_news_bot.models import DraftRecord
from ai_news_bot.storage import JsonStateStore
from ai_news_bot.telegram_api import TelegramApi


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _owner_matches(chat_id: object, owner_chat_id: object) -> bool:
    return chat_id is not None and owner_chat_id is not None and str(chat_id) == str(owner_chat_id)


def _message_chat_id(message: dict) -> object:
    chat = message.get("chat") or {}
    return chat.get("id")


def _callback_chat_id(callback: dict) -> object:
    message = callback.get("message") or {}
    return _message_chat_id(message)


def _finalize_publication(store: JsonStateStore, draft: DraftRecord) -> None:
    backlog = store.load_backlog()
    published_ids = set(draft.selected_story_ids)
    published_urls = set(store.load_published())
    for item in backlog:
        if item.item_id in published_ids:
            item.status = "published"
            published_urls.add(item.source_url)
    store.save_backlog(backlog)
    store.save_published(sorted(published_urls))
    draft.status = "published"
    store.save_current_draft(draft)


def _replace_owner_draft(owner_drafts: list[DraftRecord], draft: DraftRecord) -> list[DraftRecord]:
    updated: list[DraftRecord] = []
    replaced = False
    for existing in owner_drafts:
        if existing.draft_id == draft.draft_id:
            updated.append(draft)
            replaced = True
        else:
            updated.append(existing)
    if not replaced:
        updated.append(draft)
    return updated


def _save_owner_draft(store: JsonStateStore, draft: DraftRecord) -> list[DraftRecord]:
    owner_drafts = _replace_owner_draft(store.load_owner_drafts(), draft)
    store.save_owner_drafts(owner_drafts)
    return owner_drafts


def _find_owner_draft(store: JsonStateStore, draft_id: str) -> DraftRecord | None:
    for draft in store.load_owner_drafts():
        if draft.draft_id == draft_id:
            return draft
    return None


def _replaceable_draft_or_none(draft: DraftRecord | None) -> DraftRecord | None:
    if draft is not None and draft.status == "publishing":
        return None
    return draft


def _release_unpublished_draft_items(
    store: JsonStateStore,
    draft: DraftRecord | None,
    *,
    preserve_story_ids: set[str] | None = None,
) -> None:
    if draft is None:
        return

    preserved_ids = preserve_story_ids or set()
    selected_ids = set(draft.selected_story_ids) - preserved_ids
    if not selected_ids:
        return

    backlog = store.load_backlog()
    published_urls = set(store.load_published())
    changed = False
    for item in backlog:
        if item.item_id not in selected_ids:
            continue
        if item.status == "published" or item.source_url in published_urls:
            continue
        if item.status != "queued":
            item.status = "queued"
            changed = True

    if changed:
        store.save_backlog(backlog)


def _publish_draft(store: JsonStateStore, telegram_api: TelegramApi, channel_id: str, draft: DraftRecord) -> None:
    def _send_current_draft() -> None:
        if draft.video_url:
            telegram_api.send_video(channel_id, draft.video_url, caption=draft.current_text)
            return
        if draft.image_url:
            telegram_api.send_photo(channel_id, draft.image_url, caption=draft.current_text)
        else:
            telegram_api.send_message(channel_id, draft.current_text)

    if draft.status == "published":
        return

    if draft.status == "publishing":
        if draft.publication_state == "needs_send":
            draft.publication_state = "sending"
            store.save_current_draft(draft)
            try:
                _send_current_draft()
            except Exception:
                draft.publication_state = "needs_send"
                store.save_current_draft(draft)
                raise
            draft.publication_state = "finalize_only"
            store.save_current_draft(draft)
        _finalize_publication(store, draft)
        return

    original_status = draft.status
    original_publication_state = draft.publication_state
    if draft.status != "publishing":
        draft.status = "publishing"
        draft.publication_state = "sending"
        store.save_current_draft(draft)
        try:
            _send_current_draft()
        except Exception:
            draft.status = original_status
            draft.publication_state = original_publication_state
            store.save_current_draft(draft)
            raise

    draft.publication_state = "finalize_only"
    store.save_current_draft(draft)
    _finalize_publication(store, draft)


def _send_owner_draft_preview(telegram_api: TelegramApi, chat_id: str, draft: DraftRecord) -> None:
    reply_markup = build_draft_keyboard(draft.draft_id)
    if draft.video_url:
        telegram_api.send_video(chat_id, draft.video_url, caption=draft.generated_text, reply_markup=reply_markup)
        return
    if draft.image_url:
        telegram_api.send_photo(chat_id, draft.image_url, caption=draft.generated_text, reply_markup=reply_markup)
        return
    telegram_api.send_message(chat_id, draft.generated_text, reply_markup)


def _build_short_draft(store: JsonStateStore, item_id: str) -> DraftRecord | None:
    current_draft = _replaceable_draft_or_none(store.load_current_draft())
    if current_draft is None and store.load_current_draft() is not None:
        return None

    backlog = store.load_backlog()
    item = next((entry for entry in backlog if entry.item_id == item_id and entry.status in {"queued", "drafted"}), None)
    if item is None:
        return None

    _release_unpublished_draft_items(
        store,
        current_draft,
        preserve_story_ids={item_id},
    )
    backlog = store.load_backlog()
    item = next((entry for entry in backlog if entry.item_id == item_id and entry.status in {"queued", "drafted"}), None)
    if item is None:
        return None

    generated_text = build_short_post_text(item)
    draft = DraftRecord(
        draft_id=f"short-{item.item_id}",
        generated_text=generated_text,
        current_text=generated_text,
        selected_story_ids=[item.item_id],
        draft_type="short_post",
        status="pending",
        created_at=_now_iso(),
        category=item.category,
        header_label="Short Post",
        image_url=item.image_url,
        video_url=item.video_url,
    )
    store.save_current_draft(draft)
    _save_owner_draft(store, draft)

    for backlog_item in backlog:
        if backlog_item.item_id == item.item_id:
            backlog_item.status = "drafted"
    store.save_backlog(backlog)
    return draft


def process_updates(store: JsonStateStore, telegram_api: TelegramApi, config) -> None:
    cursor = store.load_cursor()
    updates = telegram_api.get_updates(offset=cursor + 1)

    for update in updates:
        cursor = update["update_id"]
        callback = update.get("callback_query")
        message = update.get("message")

        if callback is not None:
            if not _owner_matches(_callback_chat_id(callback), config.telegram_owner_chat_id):
                continue

            data = callback.get("data", "")
            action, _, draft_id = data.partition(":")
            draft = _find_owner_draft(store, draft_id)
            if draft is None:
                draft = store.load_current_draft()
                if draft is None or draft.draft_id != draft_id:
                    telegram_api.answer_callback(callback["id"], "Draft is no longer available")
                    continue

            store.save_current_draft(draft)
            if draft is None:
                continue
            if data == f"approve:{draft.draft_id}":
                telegram_api.answer_callback(
                    callback["id"],
                    "Scheduled approval is no longer supported; use Publish now",
                )
                continue
            if draft.status in {"published", "skipped"}:
                telegram_api.answer_callback(
                    callback["id"],
                    "Draft already published" if draft.status == "published" else "Draft already skipped",
                )
                continue
            if draft.status == "publishing":
                continue

            if data == f"edit:{draft.draft_id}":
                mark_draft_editing(draft)
                store.save_current_draft(draft)
                _save_owner_draft(store, draft)
                telegram_api.answer_callback(callback["id"], "Send replacement text as the next message")
            elif data == f"publish_now:{draft.draft_id}":
                _publish_draft(store, telegram_api, config.telegram_channel_id, draft)
                _save_owner_draft(store, draft)
                telegram_api.answer_callback(callback["id"], "Draft published immediately")
            elif data == f"skip:{draft.draft_id}":
                _release_unpublished_draft_items(store, draft)
                draft.status = "skipped"
                store.save_current_draft(draft)
                _save_owner_draft(store, draft)
                telegram_api.answer_callback(callback["id"], "Draft skipped")
            continue

        if message is None:
            continue
        if not _owner_matches(_message_chat_id(message), config.telegram_owner_chat_id):
            continue

        draft = store.load_current_draft()
        text = (message.get("text") or "").strip()

        if draft is not None and draft.status == "editing" and text:
            draft.current_text = text
            draft.status = "pending"
            store.save_current_draft(draft)
            _save_owner_draft(store, draft)
            telegram_api.send_message(
                config.telegram_owner_chat_id,
                "Draft updated. You can publish or edit again.",
                build_draft_keyboard(draft.draft_id),
            )
            continue

        command, arg = parse_owner_command(text)
        if command == "backlog":
            queued = [item for item in store.load_backlog() if item.status == "queued"][:10]
            lines = [f"{item.item_id}: {item.source_title}" for item in queued]
            telegram_api.send_message(
                config.telegram_owner_chat_id,
                "\n".join(lines) if lines else "Backlog is empty",
            )
        elif command == "short" and arg:
            short_draft = _build_short_draft(store, arg)
            if short_draft is not None:
                _send_owner_draft_preview(telegram_api, config.telegram_owner_chat_id, short_draft)
        elif command == "publish_now" and arg:
            short_draft = _build_short_draft(store, arg)
            if short_draft is not None:
                _publish_draft(store, telegram_api, config.telegram_channel_id, short_draft)

    store.save_cursor(cursor)

    draft = store.load_current_draft()
    if draft is None or draft.status == "skipped":
        return

    if draft.status == "publishing":
        _publish_draft(store, telegram_api, config.telegram_channel_id, draft)


def main() -> None:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    process_updates(store, telegram_api, config)


if __name__ == "__main__":
    main()
