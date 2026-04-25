# AI News Telegram Bot

## Required secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_CHAT_ID`
- `TELEGRAM_CHANNEL_ID`
- `OPENROUTER_API_KEY` optional, used only for AI post rewriting

Optional repository variable:
- `OPENROUTER_MODEL`, for example a model id from OpenRouter. If omitted, OpenRouter uses the account default.

## Source configuration

Discovery sources are stored in `sources.yaml`.

Supported tiers:
- `tier1_official`
- `tier2_media`
- `tier3_ai_publications`
- `tier4_community`

Supported kinds:
- `rss`
- `atom`
- `website`
- `reddit`
- `hackernews`

Community-originated topics stay out of the actionable draft flow until a stronger source confirms them.

## Current operating model

- GitHub Actions `news-watcher` is the scheduled job used in normal operation.
- `news-watcher` runs every `30` minutes and sends only fresh confirmed news drafts to the owner.
- Each run sends up to `3` items by default; change with `NEWS_WATCHER_PREVIEW_LIMIT`.
- News older than `2` hours are skipped by default; change with `NEWS_WATCHER_MAX_AGE_HOURS`.
- Sent topic fingerprints are stored in `state/sent_topics.json` to reduce repeated stories from different sources.
- Messages are sent without inline buttons; the owner edits and posts manually.
- Before sending selected previews, `news-watcher` tries to refresh article media from the source page and prefers page-level `og:video` / `og:image` over small RSS thumbnails.
- If `OPENROUTER_API_KEY` is configured, posts are rewritten through OpenRouter. If the request fails, the bot falls back to the local template.
- Telegram callback polling is not required for the normal workflow.
- Unpublished backlog items stay valid for up to `14` days; older items are dropped as stale.

## Local commands

- `python -m pytest -q`
- `python scripts/run_news_watcher.py`
- `python scripts/run_daily_slot.py`

## Optional legacy Telegram owner commands

- `/backlog`
- `/short <item_id>`
- `/publish_now <item_id>`

These commands require `scripts/run_local_polling.py`, but they are not needed when using the manual posting workflow.
