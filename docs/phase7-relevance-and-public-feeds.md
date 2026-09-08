# Phase 7 — Relevant-job ingestion and public-feed expansion

## Goal

Keep the primary jobs table focused on software-engineering opportunities and increase coverage
without requiring applicant-owned API keys.

## Implemented scope

### 1. Ingestion-time relevance gate

- Titles with explicit software roles are accepted immediately.
- Explicitly unrelated roles such as sales, office operations, recruiting, marketing, finance,
  customer support, product management, and field work are rejected before a detail request.
- Ambiguous titles are checked against description-level technology and engineering-action evidence.
- Only accepted jobs enter `job_postings` and the matching pipeline.
- Existing postings are re-evaluated when `relevance_version` changes; rejected legacy postings are
  made inactive on the next source refresh.

### 2. Rejection ledger

Rejected jobs are recorded in `job_rejections`, separate from the user-facing jobs table. The
ledger stores the provider job ID, reason, confidence, matched terms, content hash, and timestamps.
This prevents repeated detail downloads while keeping the decision auditable. A changed listing is
evaluated again, and an accepted listing is removed from the rejection ledger.

### 3. New no-key public sources

- Himalayas public Jobs API
- Jobicy public Remote Jobs API, restricted to the engineering industry
- Remotive public API, restricted to the software-development category
- We Work Remotely programming RSS feed

All adapter records preserve visible source attribution and link back to the original listing.
Provider polling limits are enforced for Himalayas (24 hours), Jobicy (1 hour), and Remotive
(6 hours). We Work Remotely uses its programming RSS feed.

### 4. Metrics and UI

Source and daily refresh runs now expose `rejected_count`. The Matches refresh card displays how
many irrelevant listings were filtered before matching.

### 5. Retention cleanup

The **All jobs** screen includes a confirmed cleanup action that permanently removes listings
older than 24 hours. Age uses the source publication timestamp when available and falls back to
the first-seen timestamp. Related match rows and snapshots are removed by database cascades;
expired rejection-ledger rows are cleaned at the same time. Surviving duplicate families retain a
canonical job. The API requires an explicit confirmation token and never permits a retention
window shorter than 24 hours.

## Deployment

1. Deploy the backend. The existing Render start command must run `alembic upgrade head` before
   Uvicorn so migration `20260908_0006` creates the ledger and new columns.
2. Call `POST /api/v1/sources/seed/phase-3` once after deployment. It adds the four new definitions
   without duplicating existing sources.
3. Deploy the frontend with its existing backend API environment variable.
4. Click **Fetch again**. The first run evaluates old postings and ingests the new feeds; later runs
   respect provider cooldowns.

## Acceptance criteria

- Obvious irrelevant titles are never written to `job_postings`.
- Ambiguous non-engineering listings are rejected after description review.
- Accepted software jobs continue through trust classification, deduplication, and resume matching.
- Rejections are auditable and can be reconsidered after source content or classifier changes.
- All four new adapters preserve attribution and require no API key.
