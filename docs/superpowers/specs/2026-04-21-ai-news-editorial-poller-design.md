# AI News Bot Editorial and Local Poller Design

Date: 2026-04-21

## Goal

Refine the current Telegram AI news bot from a digest-oriented flow into a short-form, single-post editorial system with faster button handling and richer content categories.

This revision changes three major parts of the product:

1. Editorial output changes from one digest to up to three separate post candidates.
2. Content scope expands beyond major AI news into useful finds and free offerings.
3. Telegram button handling moves from GitHub Actions polling to a local Windows poller for near-immediate response.

## Product Outcome

Each daily run should send the owner up to three separate candidate posts in Telegram. Each candidate should be short, readable, image-first when possible, and easy to publish manually through one button.

The bot should no longer optimize for a long daily digest. It should optimize for compact, channel-ready posts that are fast to scan and fast to publish.

## Content Model

### Post Types

The bot supports two editorial categories:

- `major_news`
- `freebie/useful_find`

`major_news` covers notable AI releases, research, tools, product launches, rollouts, platform changes, and other meaningful developments.

`freebie/useful_find` covers:

- free access to useful AI tools or features
- public rollouts with practical value
- open-source launches
- strong free tiers
- smaller but useful product updates
- practical AI discoveries worth trying

Both categories participate in candidate generation, but they are scored independently enough that smaller useful finds are not drowned out by larger headline news.

### Candidate Count

Each daily run should generate up to three separate candidate posts total.

This is a hard editorial preference, not a soft target:

- do not build a long digest
- do not overfill a single message
- prefer fewer strong posts over many weak posts

### Grouping Rule

Default rule:

- one post candidate equals one topic

Rare exception:

- if two topics are directly connected and clearly read better as one post, they may be merged into a single candidate

This is an exception path only and should not become the default output shape.

## Draft Delivery

### Owner Delivery Format

The bot sends candidates to the owner as separate Telegram messages, one after another.

Each candidate message must make it obvious what it is. The owner should be able to understand immediately:

- this is a draft candidate
- which candidate number it is
- what kind of post it is
- what story it covers

Recommended header style:

- `Draft 1/3 - major_news`
- `Draft 2/3 - freebie/useful_find`

The exact wording may vary, but the message must be self-identifying.

### Draft Actions

Each draft keeps only these actions:

- `Publish now`
- `Edit`
- `Skip`

Removed action:

- `Approve for 18:00`

There is no scheduled approval state anymore. The only publication mode is explicit manual publish.

### Scheduling Meaning

`18:00 Europe/Moscow` remains the time when the bot sends candidates to the owner.

It is no longer a deferred publication slot. It is now only the daily candidate generation and delivery time.

## Editorial Writing Style

### Tone

Draft text should be more human and Telegram-native than the current MVP.

The tone should be:

- short
- readable
- practical
- friendly
- slightly informal
- clear enough for quick scanning

The tone should not be:

- dry digest prose
- overly formal
- dense technical summary
- overly long list formatting

### Structure

Each single-post candidate should usually contain:

1. one clear opening line or hook
2. two to four short lines with the core value of the update
3. one source link

If a post naturally benefits from a short bullet block, that is acceptable, but the message should still feel like a compact Telegram post, not a report.

### Source Attribution

Each draft must retain a source link.

The bot should prefer the primary source when available, especially for official launches and product rollouts.

## Media Logic

Each candidate should include an image when a suitable one exists.

Image priority:

1. `og:image`
2. primary article image
3. first good page image
4. no image if nothing acceptable is available

The bot should reject clearly bad media, such as:

- tiny thumbnails
- broken links
- obvious tracking assets
- irrelevant decorative images

If no decent image is found, the post should still be sent as text-only.

## Discovery and Ranking Adjustments

The existing multi-tier discovery system remains in place, but ranking must be extended to support editorial categories.

### Existing Source Model

The bot continues using the curated source registry in `sources.yaml` across four tiers:

- official
- major media
- AI publications
- community

The owner may continue adding custom sources manually later by editing `sources.yaml`.

### New Classification Layer

Each candidate should be classified into one of:

- `major_news`
- `freebie/useful_find`

This classification should be derived from source, title, summary, and keyword cues.

Signals for `freebie/useful_find` include terms such as:

- free
- open-source
- available now
- public beta
- public rollout
- free tier
- released for everyone
- no waitlist
- try it now

Signals for `major_news` include terms such as:

- launch
- release
- model
- benchmark
- enterprise
- funding
- API
- acquisition
- regulation
- major product update

The exact keyword set can evolve, but the system must be able to distinguish practical smaller finds from larger industry news.

### Selection Logic

The daily run should select up to three strongest candidates overall, with a preference for variety across the two categories when both are available.

Example desired behavior:

- 2 strong major news items + 1 useful find
- 1 major news item + 2 useful finds
- only 1 or 2 total candidates if the day is weak

The bot should never force three posts if the available material is weak.

## Windows Local Poller

### Why This Changes

GitHub Actions is acceptable for once-daily candidate generation, but it is a poor fit for handling Telegram button presses in near real time.

The current GitHub poller introduces unpredictable delays because scheduled workflows do not run precisely and may lag by several minutes.

### New Poller Model

The GitHub workflow for `poll-telegram` should be disabled entirely.

Telegram button processing moves to a local Windows poller that:

- runs after user login
- polls Telegram every 30 seconds
- processes `Publish now`, `Edit`, and `Skip`
- can be started and stopped independently of the rest of the system

### Startup Model

The local poller should be registered in Windows Task Scheduler with this behavior:

- trigger: at logon of the user
- run in background
- restart automatically if needed

This keeps the system simple and avoids requiring a VPS.

### Operational Tradeoff

If the PC is off or the user is not logged in:

- `daily-slot` still works through GitHub Actions
- new drafts still arrive
- buttons will not process until the local poller is running again

This tradeoff is acceptable for the no-cost architecture.

## State and Action Model

Draft states should be simplified after removing scheduled approval.

Practical states:

- `pending`
- `editing`
- `publishing`
- `published`
- `skipped`

Removed state path:

- scheduled approval for a future slot

This simplification reduces branching in the polling and draft lifecycle logic.

## Non-Goals

This revision does not include:

- automatic posting without user action
- Telegram-based source management
- LLM integration
- fully autonomous topic clustering
- instant processing when the Windows poller is offline

## Testing Requirements

The implementation should verify:

- daily run creates up to three separate single-post drafts
- drafts are labeled clearly for owner review
- `Approve for 18:00` no longer exists
- category selection supports both `major_news` and `freebie/useful_find`
- media extraction chooses a usable image when available
- local poll loop processes Telegram updates repeatedly
- GitHub `poll-telegram` no longer competes for updates

## Acceptance Criteria

This revision is successful when:

1. The owner receives up to three separate short-form post drafts per daily run.
2. Drafts read like compact Telegram posts rather than digest entries.
3. Useful free offerings and practical AI finds can appear alongside major news.
4. Each draft can include an image when a suitable one exists.
5. Button presses are handled by the Windows local poller without manual GitHub workflow runs.
6. The GitHub-hosted daily discovery flow remains free and operational.
