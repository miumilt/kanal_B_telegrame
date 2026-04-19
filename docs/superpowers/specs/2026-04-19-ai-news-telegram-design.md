# AI News Telegram Channel Design

Date: 2026-04-19
Status: Draft for user review

## Goal

Build a no-cost MVP for a Telegram news channel about AI centered on a daily editorial slot at 18:00 Moscow time. The system should gather relevant news from English-language web sources, accumulate candidate items in a backlog, prepare a Russian draft built from the best available items, send that draft to the owner in a personal Telegram chat, allow the owner to edit the text, and publish to the channel only after explicit approval.

## Scope

### In Scope

- Daily digest in Russian.
- Source discovery from broad English-language web search.
- Search window of the last 3-4 days instead of only the last 24 hours.
- Selection of 3-5 strong news items for each digest.
- Balance of major news plus interesting new releases and research.
- Delivery of the draft to the owner in a private Telegram chat.
- Telegram approval action before channel publication.
- Owner draft editing before publication.
- Basic storage of publication history and current draft state.
- Backlog storage for accumulated unpublished news items.
- Basic logging for operations and debugging.

### Out of Scope

- Fully autonomous publication without approval.
- Audience growth automation.
- Paid traffic acquisition or Telegram Ads setup.
- Cross-posting to other platforms.
- Advanced analytics dashboards.
- AI-generated images or cover art.
- Real-time continuous monitoring of news.

## Product Decisions

- Publishing model: semi-automatic with backlog accumulation.
- Hosting: no-cost infrastructure.
- Runtime choice: GitHub Actions on a daily schedule.
- Publishing time: 18:00 Europe/Moscow.
- Draft approval flow: draft sent to owner in personal Telegram chat, optionally edited by the owner, then published after explicit Telegram approval. Preferred UX is inline buttons if they can be implemented without breaking the no-cost constraint.
- Source language: English.
- Publication language: Russian.
- Content format: primary daily slot at 18:00 with either a 3-5 item digest or a short single-item post when appropriate.
- Search strategy: broad web search with topic filtering, not a fixed whitelist.
- Editorial strategy: balanced selection of major stories plus interesting fresh releases and research.

## Recommended Architecture

The MVP uses a scheduled GitHub Actions workflow as the orchestrator. On a daily cadence, the workflow runs a Python pipeline that searches for AI-related news from the last 3-4 days, extracts candidate stories, removes duplicates, ranks stories, and stores valid items in a backlog. For the primary 18:00 Moscow editorial slot, the system builds a Russian draft from the best currently available backlog items and sends the result to the owner in Telegram. The owner reviews the draft in a private chat, may edit the text, and explicitly approves publication. Only after that action does the bot publish to the Telegram channel. The system may also support owner-triggered manual publication of a shorter post outside the main slot when a backlog item is worth posting separately.

### Main Components

1. Scheduler
   - GitHub Actions scheduled workflow.
   - Triggered daily at 18:00 Moscow time.

2. News collection module
   - Runs broad web search queries around AI topics.
   - Fetches candidate article pages and metadata.
   - Collects title, URL, source, publish date, and article text snippet.

3. Filtering and ranking module
   - Removes obvious spam, duplicates, and low-signal stories.
   - Scores items by freshness, significance, source trust, audience relevance, and discussion value.
   - Limits overrepresentation from the same topic category.

4. Digest generation module
   - Produces Russian-language summaries from selected English-language inputs.
   - Formats either a digest or a short single-item post, depending on backlog quality and editorial choice.
   - Includes a short introduction plus 3-5 news entries with source links for digest mode.

5. State storage
   - Stores backlog items, recent published URLs, semantic fingerprints or normalized titles, current draft, and publication status.
   - Needs only lightweight file-based storage for MVP.

6. Telegram delivery module
   - Sends the draft to the owner in a personal Telegram chat.
   - Adds owner controls such as `Approve for 18:00`, `Publish now`, `Skip`, and `Edit`.
   - Accepts edited draft text from the owner and stores the revised version.
   - On `Approve for 18:00`, keeps the draft approved for the next scheduled slot.
   - On `Publish now`, posts the latest saved version of the draft text to the target channel immediately.
   - Optionally allows owner-initiated handling of backlog items outside the main daily slot.

7. Logging module
   - Records run time, candidates found, items filtered out, selected stories, draft send status, and publication result.

## News Selection Logic

### Search Window

The system searches over the last 3-4 days rather than only the last 24 hours. This prevents empty or weak digests on slow news days and allows strong stories that were missed on day one to still appear.

### Story Categories

The collector should consider these categories:

- model launches and upgrades;
- product releases and tooling updates;
- open-source AI projects;
- research papers and benchmark results;
- funding, acquisitions, and partnerships;
- regulation and policy;
- notable failures, incidents, or controversies.

### Ranking Criteria

Each candidate item should be ranked using a weighted heuristic:

- freshness;
- significance to the AI ecosystem;
- source trustworthiness;
- usefulness to the channel audience;
- likelihood that the topic is genuinely being discussed;
- novelty relative to recently published channel content.

### Diversity Rule

One main-slot draft should not be dominated by a single subtopic. For example, five nearly identical model API release notes should not fill the whole post. The pipeline should cap same-type items so the output remains varied.

### Duplicate Control

The system should detect duplicates by:

- exact URL match;
- normalized title similarity;
- semantic similarity for near-identical stories reported by multiple sites.

If several sites cover the same event, the system should collapse them into one story and keep the best source reference.

## Draft Format

The primary output should be concise and readable in Telegram.

Recommended digest structure:

1. Short opening line framing the daily digest.
2. Three to five news blocks.
3. Each block contains:
   - a Russian headline;
   - a short explanation of what happened;
   - a short explanation of why it matters;
   - a source link.

Recommended short-post structure:

1. One concise Russian headline.
2. One short explanation of what happened.
3. One short note on why it matters.
4. One source link.

The tone should be informative and compact, not inflated or overly promotional.

## Approval and Publishing Flow

1. GitHub Actions gathers and ranks candidate stories from the last 3-4 days and stores valid ones in the backlog.
2. For the main 18:00 Moscow slot, the system selects the best current backlog items.
3. The system generates either a Russian digest draft or a short single-item post.
4. The bot sends the draft to the owner in a private Telegram chat.
5. The owner can `Edit`, `Approve for 18:00`, `Publish now`, `Skip`, or leave the draft unpublished.
6. If the owner edits the draft, the system stores the revised text as the current publishable version.
7. On `Approve for 18:00`, the draft waits for the scheduled slot and is then published automatically if still valid.
8. On `Publish now`, the bot posts the latest approved draft text to the Telegram channel immediately.
9. Published items are marked as used and removed from future selection.
10. Unpublished items remain in backlog until they are published, skipped, or expired.

## Reliability and Failure Handling

- If the search step returns too few strong stories for a full digest, the system should send a reduced digest or a short single-item post instead of inventing weak content.
- If sources are inaccessible, badly parsed, or suspicious, those items should be dropped.
- If the summarization result is low quality, the system should retry generation before sending the draft.
- If the owner edits the draft, the edited version must replace the generated version for future publish actions until a newer draft is created.
- The `Publish` action must be bound to the current active draft only, so an old draft cannot be published accidentally.
- `Approve for 18:00` and `Publish now` must be distinct actions with distinct outcomes so the owner can choose delayed or immediate release intentionally.
- If Telegram delivery fails, the run should log the failure clearly for manual inspection.
- If publication to the channel fails after approval, the system should preserve the approved draft and mark the publish attempt as failed rather than discard state.
- Backlog items must expire after a defined freshness window so stale topics do not remain eligible forever.

## Data Model

The MVP can use simple file-based JSON storage. Suggested records:

- `backlog_items`
  - item id
  - source URL
  - source title
  - normalized title
  - topic fingerprint
  - source name
  - publish date
  - summary candidate
  - status: new, queued, drafted, published, skipped, expired
  - first seen timestamp
  - last considered timestamp

- `published_items`
  - source URL
  - normalized title
  - topic fingerprint
  - publication date

- `current_draft`
  - draft id
  - generated text
  - editable current text
  - selected story ids
  - draft type: digest or short_post
  - creation timestamp
  - status: pending, editing, published, skipped, failed

- `run_log`
  - run timestamp
  - candidate count
  - selected count
  - errors
  - send status
  - publish status

## Quality Bar

The MVP is successful if:

- the workflow consistently prepares the main-slot draft for the daily 18:00 Moscow editorial cycle;
- the owner receives a usable Telegram draft in a private chat;
- the owner can revise draft text before publication without losing the draft state;
- the system usually proposes either a strong 3-5 item digest or a valid short post when the news day is weak;
- stories are not obvious duplicates or low-value filler;
- publication to the channel happens through one approval action;
- recently covered topics are not repeated unnecessarily;
- unpublished topics remain available in backlog until they are no longer worth posting.

## Tradeoffs and Rationale

### Why GitHub Actions

This approach matches the no-cost requirement and the daily editorial schedule. It avoids maintaining a full-time server while still providing sufficient automation for backlog collection and a primary publication slot.

### Why Semi-Automatic Instead of Fully Automatic

Editorial quality is the main risk in this project. Human approval keeps the channel from publishing weak, repetitive, misleading, or badly summarized content. This is the correct tradeoff for an MVP.

### Why Broad Search Instead of Fixed Sources

A fixed source list is safer but too restrictive for the stated goal. Broad search is necessary to catch important launches, research, and ecosystem changes such as new CLI tools, open-source releases, or notable industry moves that may not come from a small source list.

## Risks

- Search quality may be noisy without good filtering.
- Some stories may appear late or with inconsistent publish dates.
- Telegram callback handling may require careful design because GitHub Actions is not a permanent server.
- LLM summarization can introduce weak phrasing or factual distortion if prompts and validation are insufficient.
- Free infrastructure is good enough for daily automation but not for low-latency event monitoring.
- Backlog accumulation can drift into clutter if expiry and ranking rules are weak.

## MVP Boundary

The first implementation should focus only on:

- scheduled daily run;
- candidate discovery;
- backlog accumulation and lifecycle management;
- filtering and ranking;
- Russian drafting for both digest and short-post modes;
- Telegram private draft delivery;
- approval-based publication;
- state tracking and basic logs.

Do not include channel growth automation, analytics, image generation, or full autonomy in the first version.

## Open Design Constraint

The approval step implies the system needs a callback path or owner command flow for Telegram approval and editing. Because GitHub Actions is not a permanent HTTP service, implementation planning must choose one of these patterns:

1. Polling-based command flow where the bot checks for owner commands and processes approval asynchronously.
2. A minimal webhook endpoint hosted elsewhere while keeping the main generation pipeline in GitHub Actions.
3. A publish token or command-based fallback where draft approval is performed via bot command rather than inline webhook callback.

The implementation plan must resolve this constraint without violating the no-cost requirement.
