# AI News Telegram Bot

## Required secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_CHAT_ID`
- `TELEGRAM_CHANNEL_ID`

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

- GitHub Actions `daily-slot` is the only scheduled GitHub job used in normal operation.
- `daily-slot` runs at `06:00 Europe/Moscow` and sends up to `10` separate single-post news drafts to the owner by default.
- `daily-slot` auto-selects only topics from the last `24` hours.
- The preview limit can be changed with `DAILY_SLOT_PREVIEW_LIMIT`.
- Messages are sent without inline buttons; the owner edits and posts manually.
- Before sending selected previews, `daily-slot` tries to refresh article media from the source page and prefers page-level `og:video` / `og:image` over small RSS thumbnails.
- Telegram callback polling is not required for the normal workflow.
- Unpublished backlog items stay valid for up to `14` days; older items are dropped as stale.

## Local commands

- `python -m pytest -q`
- `python scripts/run_daily_slot.py`

## Optional legacy Telegram owner commands

- `/backlog`
- `/short <item_id>`
- `/publish_now <item_id>`

These commands require `scripts/run_local_polling.py`, but they are not needed when using the manual posting workflow.
