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
- `daily-slot` runs at `18:00 Europe/Moscow` and sends up to `3` separate single-post owner previews.
- `daily-slot` auto-selects only topics from the last `24` hours.
- The first preview becomes the persisted actionable draft.
- Additional previews are owner-facing suggestions; they are not persisted as separate actionable drafts.
- Draft buttons are only `Edit`, `Publish now`, and `Skip`.
- Telegram callback processing now runs locally on Windows through `scripts/run_local_polling.py`.
- Unpublished backlog items stay valid for up to `14` days; older items are dropped as stale.

## Local commands

- `python -m pytest -q`
- `python scripts/run_daily_slot.py`
- `python scripts/run_local_polling.py`

## Telegram owner commands

- `/backlog`
- `/short <item_id>`
- `/publish_now <item_id>`
- Press `Edit`, then send replacement text as the next message
- Press `Publish now`
- Press `Skip`

## Windows local poller

Run the local poller from the repository root:

```powershell
cd C:\Users\qqqma\OneDrive\Desktop\kanal_B_telegrame
python scripts/run_local_polling.py
```

The poller reads `TELEGRAM_POLL_INTERVAL_SECONDS` from the environment and defaults to `30` seconds.

## Task Scheduler setup

Recommended Windows Task Scheduler settings:

- Trigger: `At log on`
- Action: start `python` with argument `scripts/run_local_polling.py`
- Start in: `C:\Users\qqqma\OneDrive\Desktop\kanal_B_telegrame`
- Run only when user is logged on
- Restart on failure: enabled

If the PC is off or you are not logged in, button presses will wait until the local poller starts again.
