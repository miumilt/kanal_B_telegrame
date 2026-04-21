# AI News Telegram Bot

## Required secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_CHAT_ID`
- `TELEGRAM_CHANNEL_ID`

## Source Configuration

Discovery sources are stored in `sources.yaml`.

Supported source tiers:
- `tier1_official`
- `tier2_media`
- `tier3_ai_publications`
- `tier4_community`

Supported source kinds:
- `rss`
- `atom`
- `website`
- `reddit`
- `hackernews`

Community-originated topics are tracked, but they are not eligible for drafting
until at least one stronger source confirms the same topic.

## Local commands

- `python -m pytest -q`
- `python scripts/run_daily_slot.py`
- `python scripts/poll_telegram_updates.py`

The daily slot job generates the draft before publication time. `Approve for 18:00`
means the post will be published at 18:00 Moscow, even though the draft job runs earlier.

## Telegram owner commands

- `/backlog`
- `/short <item_id>`
- `/publish_now <item_id>`
- Press `Edit`, then send replacement text as the next message
- Press `Approve for 18:00`
- Press `Publish now`
