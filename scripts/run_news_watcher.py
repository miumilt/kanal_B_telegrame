from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ai_news_bot.backlog import merge_candidates, select_watcher_items
from ai_news_bot.config import load_config
from ai_news_bot.drafts import build_single_post_text
from ai_news_bot.media import extract_media_urls
from ai_news_bot.models import BacklogItem
from ai_news_bot.rewriter import maybe_rewrite_post
from ai_news_bot.storage import JsonStateStore
from ai_news_bot.telegram_api import TelegramApi

from run_daily_slot import BACKLOG_EXPIRY_DAYS, _refresh_selected_media, _send_owner_draft_preview


WATCHER_MAX_AGE_HOURS = 2
WATCHER_PREVIEW_LIMIT = 3


def refresh_backlog(
    store: JsonStateStore,
    *,
    now_iso: str,
    fetcher,
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


def _build_manual_post(
    item: BacklogItem,
    *,
    openrouter_api_key: str | None = None,
    openrouter_model: str | None = None,
) -> str:
    fallback = build_single_post_text(item)
    return maybe_rewrite_post(
        item,
        fallback,
        api_key=openrouter_api_key,
        model=openrouter_model,
    )


def _mark_sent(store: JsonStateStore, sent_items: list[BacklogItem]) -> None:
    if not sent_items:
        return

    sent_ids = {item.item_id for item in sent_items}
    sent_urls = {item.source_url for item in sent_items}
    sent_topics = {item.topic_fingerprint for item in sent_items if item.topic_fingerprint}

    backlog = store.load_backlog()
    for item in backlog:
        if item.item_id in sent_ids or item.topic_fingerprint in sent_topics:
            item.status = "published"
    store.save_backlog(backlog)

    published = list(dict.fromkeys(store.load_published() + sorted(sent_urls)))
    store.save_published(published)

    known_topics = list(dict.fromkeys(store.load_sent_topics() + sorted(sent_topics)))
    store.save_sent_topics(known_topics)


def run_news_watcher(
    store: JsonStateStore,
    *,
    telegram_api: TelegramApi | None = None,
    owner_chat_id: str | None = None,
    now_iso: str | None = None,
    fetcher,
    preview_limit: int = WATCHER_PREVIEW_LIMIT,
    max_age_hours: int = WATCHER_MAX_AGE_HOURS,
    media_refresher=None,
    openrouter_api_key: str | None = None,
    openrouter_model: str | None = None,
) -> list[BacklogItem]:
    current_now_iso = now_iso or datetime.now(UTC).isoformat()
    backlog = refresh_backlog(store, now_iso=current_now_iso, fetcher=fetcher)
    selected = select_watcher_items(
        backlog,
        sent_topics=set(store.load_sent_topics()),
        limit=preview_limit,
        now_iso=current_now_iso,
        max_age_hours=max_age_hours,
    )
    selected = _refresh_selected_media(selected, media_refresher=media_refresher)

    sent: list[BacklogItem] = []
    for item in selected:
        text = _build_manual_post(
            item,
            openrouter_api_key=openrouter_api_key,
            openrouter_model=openrouter_model,
        )
        if telegram_api is not None and owner_chat_id:
            from ai_news_bot.models import DraftRecord

            draft = DraftRecord(
                draft_id=item.item_id,
                generated_text=text,
                current_text=text,
                selected_story_ids=[item.item_id],
                draft_type="manual_post",
                status="published",
                created_at=current_now_iso,
                category=item.category,
                header_label="Manual Post",
                image_url=item.image_url,
                video_url=item.video_url,
            )
            _send_owner_draft_preview(telegram_api, owner_chat_id, draft)
        sent.append(item)

    _mark_sent(store, sent)
    return sent


def main() -> list[BacklogItem]:
    config = load_config()
    store = JsonStateStore(config.state_dir)
    telegram_api = TelegramApi(config.telegram_bot_token)
    from ai_news_bot.discovery import fetch_candidates, fetch_page_html

    def media_refresher(url: str) -> tuple[str | None, str | None]:
        html = fetch_page_html(url)
        if not html:
            return (None, None)
        return extract_media_urls(html, url)

    return run_news_watcher(
        store,
        telegram_api=telegram_api,
        owner_chat_id=config.telegram_owner_chat_id,
        fetcher=lambda now_iso: fetch_candidates(now_iso, sources_path=config.sources_path),
        preview_limit=config.news_watcher_preview_limit,
        max_age_hours=config.news_watcher_max_age_hours,
        media_refresher=media_refresher,
        openrouter_api_key=config.openrouter_api_key,
        openrouter_model=config.openrouter_model,
    )


if __name__ == "__main__":
    main()
