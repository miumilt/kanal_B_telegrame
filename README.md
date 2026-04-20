# AI News Telegram Bot

## Required secrets

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_OWNER_CHAT_ID`
- `TELEGRAM_CHANNEL_ID`

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
