# AI News Discovery Expansion Design

Date: 2026-04-20
Status: Draft for user review

## Goal

Replace the current narrow discovery layer with a larger, structured, no-cost source pipeline that can reliably surface AI news from a broad set of official, media, publication, and community sources without requiring a paid LLM API.

The upgraded system should keep the existing Telegram editorial workflow intact while making the candidate pool substantially stronger and more diverse.

## Why This Change Exists

The current MVP discovery logic depends on a small set of broad Google News RSS queries. That is too weak for the intended channel quality because:

- candidate coverage is too narrow and inconsistent;
- official product launches can be missed;
- community discussions are not integrated as signals;
- source quality is not explicitly modeled;
- the system cannot distinguish between trusted news and unverified noise.

The expanded design keeps the free-hosting constraint while moving discovery from a simple search-query model to a curated multi-source intake model.

## Scope

### In Scope

- Large curated source pool stored outside code.
- Source metadata stored in `JSON` or `YAML`, with `YAML` preferred.
- Four source tiers:
  - `tier1_official`
  - `tier2_media`
  - `tier3_ai_publications`
  - `tier4_community`
- Source kinds such as:
  - `rss`
  - `atom`
  - `website`
  - `reddit`
  - `hackernews`
- Discovery pipeline that reads configured sources and normalizes all collected items into a common internal format.
- Tier-aware ranking and eligibility logic.
- Verification rule that community-originated topics require confirmation from at least one stronger source before publication.
- Deduplication across sources and tiers.
- Backlog accumulation of confirmed and observed items.
- Free operation inside the existing GitHub Actions model.

### Out of Scope

- Full web scraping of arbitrary HTML pages with per-site custom parsers for hundreds of unsupported sites.
- X/Twitter scraping.
- YouTube discovery and transcript extraction.
- Paid news APIs.
- LLM-based scoring or summarization.
- Embedding-based semantic clustering.
- Automatic source discovery from the whole web.

## Product Decisions

- Cost model: fully free.
- LLM usage: none in this phase.
- Source list storage: external `sources.yaml`.
- Discovery strategy: mixed feeds, not search-only and not wide HTML scraping.
- Community policy: all four tiers participate, but `tier4` items can only become publishable if at least one non-community source confirms the same topic.
- Editorial continuity: existing digest, short-post, backlog, draft approval, edit, and publish flows remain unchanged.

## Source Architecture

### Source File

The system will load sources from a dedicated `sources.yaml` file. The file must be editable without changing Python code.

Each source record should include:

- `id`
- `name`
- `tier`
- `kind`
- `url`
- `feed_url`
- `language`
- `priority`
- `enabled`
- `tags`

Optional fields may include:

- `notes`
- `topic_filters`
- `include_patterns`
- `exclude_patterns`

### Tier Definitions

#### `tier1_official`

Primary sources published by the organizations creating the models, products, or policies being discussed.

Examples:

- OpenAI
- Anthropic
- Google AI
- Google DeepMind
- Meta AI
- Microsoft AI
- xAI
- Hugging Face
- Mistral
- NVIDIA
- GitHub
- ElevenLabs
- Stability AI

These sources receive the highest trust weight for confirmation and ranking.

#### `tier2_media`

General technology and business media with strong reporting value.

Examples:

- TechCrunch
- The Verge
- Ars Technica
- Wired
- VentureBeat
- Reuters Tech
- Bloomberg Tech
- Financial Times Tech
- Engadget
- MIT Technology Review

These sources are used both as direct candidate sources and as confirmation evidence.

#### `tier3_ai_publications`

AI-focused publications, newsletters, paper aggregators, and industry-specific feeds.

Examples:

- The Batch
- Ben's Bites
- AI News
- MarkTechPost
- Papers with Code
- selected Hugging Face publication feeds

These sources are useful for broader coverage and trend discovery but have lower base trust than `tier1` and `tier2`.

#### `tier4_community`

Community discussions, user threads, comment-driven signals, and launch chatter.

Examples:

- relevant Reddit communities
- Hacker News threads
- public launch and discussion feeds

These sources are not discarded. They are part of the system and influence ranking, but require confirmation before they can become publishable items.

## Discovery Pipeline

### Intake

For each enabled source:

1. Load feed or source metadata from `sources.yaml`.
2. Fetch entries using the source-specific intake strategy.
3. Extract candidate fields:
   - title
   - source URL
   - source name
   - publication timestamp
   - text summary or snippet
   - source tier
   - source kind
4. Normalize all results into the shared internal story format.

### Preferred Intake Modes

- `rss` and `atom` are the primary supported modes.
- `reddit` and `hackernews` should use public feeds or public endpoints where possible.
- `website` should be limited to sources that expose stable list pages or lightweight fetchable content without requiring a heavy custom scraping stack.

This keeps the system inside the free and maintainable boundary.

### Internal Candidate Model

The existing backlog item shape can be extended with source metadata such as:

- `source_tier`
- `source_kind`
- `priority`
- `topic_signals`
- `evidence_urls`
- `confirmed`

The pipeline should still produce a single unified item type so downstream logic stays simple.

## Ranking And Verification Logic

### Base Scoring

Each candidate receives score contributions from:

- freshness
- source tier
- source priority from `sources.yaml`
- event keywords
- topic diversity value
- amount of independent corroboration
- community attention

### Topic Categories

Scoring should recognize at least these event types:

- model release
- model update
- API launch
- CLI or developer tool
- benchmark or research result
- open-source release
- funding or acquisition
- regulation or policy
- failure or controversy

### Confirmation Rule

If a topic is first seen in `tier4_community`, it becomes an observed item, not an eligible publication candidate.

It becomes eligible only after at least one source from `tier1_official`, `tier2_media`, or `tier3_ai_publications` confirms the same topic.

This confirmation can be implemented by shared normalized titles, fingerprints, or matching topic keys.

### Community Influence

Community sources should still matter:

- they can raise the score of an already confirmed topic;
- they can surface topics before media or official channels publish them;
- they can act as signals for tracking likely important stories.

But they cannot directly bypass verification.

## Deduplication

Deduplication must operate across all tiers and all source kinds.

The system should deduplicate by:

- exact source URL
- normalized title
- topic fingerprint

When several sources cover the same topic:

- one source becomes the primary reference for publication;
- the others are retained as evidence;
- the item score and confidence can be raised accordingly.

Primary-source preference should generally favor:

1. `tier1_official`
2. `tier2_media`
3. `tier3_ai_publications`
4. `tier4_community`

unless a lower-tier source clearly contains the original material and a higher-tier source is only a repost.

## Backlog Behavior

The backlog remains the system of record for candidate items.

Expected statuses now include both publishability and lifecycle state:

- `new`
- `queued`
- `drafted`
- `published`
- `skipped`
- `expired`
- `observed_unconfirmed`

Rules:

- confirmed items can become `queued`;
- `tier4` items without confirmation remain `observed_unconfirmed`;
- stale items expire after the configured freshness window;
- unpublished confirmed items can continue to compete in later runs until they expire or are used.

## Start-Up Source Set

The first upgraded source file should ship with a large initial pool, not an empty framework.

The starting configuration should include dozens of sources distributed across all tiers, with emphasis on:

- major official AI vendors and labs;
- major tech media;
- AI-specific publications and paper/news aggregators;
- Reddit and Hacker News feeds where practical.

The initial goal is breadth with structure, not perfect completeness. The file should be designed for straightforward expansion over time.

## Reliability And Failure Handling

- Individual source fetch failures must not fail the whole run.
- Disabled or broken sources should be easy to turn off in `sources.yaml`.
- Empty output from one tier must not block the others.
- If no eligible confirmed items exist, the system should still complete successfully and notify the owner that no draft was produced.
- Community-only chatter without confirmation should remain visible in backlog or logs, not silently disappear.

## Testing Requirements

The upgraded discovery system should be verified with tests covering:

- source file parsing
- intake across several source kinds
- deduplication across tiers
- confirmation logic for `tier4`
- ranking behavior when the same topic is seen across multiple sources
- backlog state transitions for confirmed and unconfirmed items
- empty-day behavior

## Recommended Implementation Direction

The correct implementation path is:

1. introduce `sources.yaml` and source loader support;
2. refactor discovery from query-based intake to source-driven intake;
3. add tier and source metadata to normalized candidates;
4. add confirmation logic for community-originated topics;
5. update ranking and backlog lifecycle rules;
6. keep the existing draft-generation and Telegram workflow unchanged unless required by the new candidate model.

This keeps the change set focused on discovery quality rather than reopening the publishing architecture.

## Risks

- A very large source pool increases noise unless source priorities are maintained carefully.
- Some feeds may be unstable or disappear over time.
- Community feeds can overwhelm the system if not properly bounded.
- Website-only sources without reliable feeds may tempt the design toward scraping complexity. That should be resisted in this phase.

## MVP Boundary For This Upgrade

This improvement is successful if:

- the system reads sources from an external YAML file;
- it collects candidates from a substantially larger, tiered source pool;
- community items require confirmation before they can be published;
- backlog quality improves enough that daily runs usually surface eligible content;
- the rest of the editorial pipeline continues to work without redesign.

This phase does not attempt to solve all content-quality problems. It upgrades discovery quality within the free architecture so later additions, including optional LLM rewriting, can sit on top of a stronger base.
