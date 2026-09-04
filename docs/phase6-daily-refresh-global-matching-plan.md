# Phase 6 plan — Daily refresh and trustworthy global matching

Status: **implemented; verification recorded separately**

## 1. Goal

Add one user-triggered workflow that fetches the latest jobs from every enabled source, safely
updates the canonical job store, classifies geographic eligibility, scores the eligible jobs
against the current resume profile, and returns the new ranked matches.

The default result must favor jobs that can be performed from Pakistan. A separate stricter view
must show only roles explicitly open worldwide. A bare `Remote` label must never be treated as
proof of worldwide eligibility.

## 2. Current gaps this phase addresses

- Ingestion can currently be started only one source at a time through
  `POST /api/v1/sources/{source_id}/ingest`.
- Ingestion and `POST /api/v1/matches/rebuild` are separate operations, so newly fetched jobs do
  not automatically appear as updated matches.
- `/matches` is rendered as a read-only server page and has no refresh action or progress state.
- `remote_mode` describes workplace mode, but the current eligibility model does not represent
  worldwide, country-list, regional, and unknown geographic scopes separately.
- The positive phrase `work from anywhere` can currently override the restrictive continuation
  `within this region`. This is the cause of North America/Europe roles appearing as eligible.
- A job first seen today is not necessarily published today. The UI needs to keep these concepts
  separate, especially for Lever, whose public feed has no authoritative publication timestamp.

## 3. Non-goals

- No automatic job applications or form submission.
- No employer-side application API keys.
- No scheduled/background refresh in this phase; the user starts the refresh with a button.
- No change to the original resume PDF or invention of candidate experience.
- No claim that `APAC`, `EMEA`, a timezone, or a generic `Remote` label includes Pakistan unless
  the employer provides supporting country-level evidence.

## 4. Target user flow

1. The user opens `/matches` and clicks **Fetch today's jobs**.
2. The button becomes disabled and the page shows the active refresh stage and source progress.
3. The backend fetches all enabled registered sources with bounded concurrency.
4. Each successful source run stores new/changed jobs, snapshots, closures, and source health by
   using the existing atomic ingestion path.
5. New and changed jobs are reclassified with the Phase 6 geographic eligibility rules.
6. Canonicalization/deduplication completes before scoring.
7. The current resume profile is loaded and matches are rebuilt automatically.
8. The UI refreshes and shows counts for verified-today jobs, newly discovered jobs, worldwide
   jobs, Pakistan-eligible jobs, unclear jobs, new matches, and failed sources.
9. The user can inspect the exact evidence that caused a role to be included or excluded.

If no current resume profile exists, ingestion still completes. The refresh ends with
`completed_without_matching` and the UI asks the user to create a profile before rebuilding
matches.

## 5. Delivery subphases

### Phase 6.1 — Data model and contracts

Add a migration and models for an orchestrated refresh run.

`refresh_runs`:

- `id`, `status`, `trigger` (`manual` initially), `started_at`, `finished_at`
- `stage` (`queued`, `ingesting`, `classifying`, `deduplicating`, `matching`, `completed`)
- source totals: attempted, succeeded, failed, skipped/circuit-open
- job totals: received, new, changed, unchanged, deactivated
- trust totals: worldwide, Pakistan-eligible, restricted, unclear, verified-today
- match totals: scored, new visible, strict visible, uncertain visible, excluded
- bounded `error_summary` and a JSON list of failed source IDs/messages

Link each existing `source_runs` record to an optional `refresh_run_id`. Preserve the existing
per-source transaction and audit history. Do not create a second ingestion implementation.

Extend `job_postings` with:

- `geographic_scope`: `worldwide`, `country_list`, `region`, `single_country`, or `unknown`
- `allowed_country_codes` and `excluded_country_codes` using normalized ISO alpha-2 codes
- `allowed_regions`
- `residency_required` and `work_authorization_required`
- `timezone_constraints`
- `global_remote`: explicit worldwide access with no country exclusions
- `eligibility_confidence`: `high`, `medium`, or `low`
- structured geographic positive, restrictive, and conflicting evidence

Keep `remote_mode` independent. Derive `pakistan_eligibility` from the new structured facts for
backward compatibility with existing filters and match records.

Planned API contracts:

- `POST /api/v1/refresh-runs` — start one refresh and return `202` plus the run ID
- `GET /api/v1/refresh-runs/{run_id}` — return progress, counts, failures, and final summary
- `GET /api/v1/refresh-runs/latest` — restore the most recent state after a page reload
- `GET /api/v1/matches` — add `scope=worldwide|pakistan|unclear` and `refresh_run_id`

Only one active refresh is permitted. A second start request returns the existing active run
rather than fetching every source twice.

### Phase 6.2 — Geographic eligibility classifier v2

Parse workplace mode and geographic eligibility as separate dimensions. Use this evidence order:

1. Structured ATS location/country fields and secondary locations.
2. Explicit eligibility or restriction sentences in the job description.
3. Public application-question metadata when available without submitting an application.
4. Generic remote wording only when it does not conflict with stronger evidence.

Restriction evidence always wins over a generic positive fragment. If evidence genuinely
conflicts, classify the job as `unknown`; do not guess.

High-confidence worldwide evidence includes:

- `worldwide`
- `anywhere in the world`
- `work from any country`
- an equivalent explicit global statement with no geographic exclusion

High-confidence Pakistan evidence includes:

- Pakistan/`PK` in an explicit allowed-country list
- explicit worldwide eligibility with no Pakistan exclusion
- a worldwide-except list in which Pakistan is not excluded; this is Pakistan-eligible but not
  `global_remote=true`

Restrictive evidence includes:

- `based`, `located`, `resident`, or `must live` in a named country/region
- `within this region`, `within these regions`, or `remote in/within ...`
- country/region-only wording such as US-only, North America, Europe, EU, UK, LATAM, or Canada
- local work authorization, payroll, tax residency, or right-to-work requirements

`APAC` and `EMEA` remain `unknown` for Pakistan unless the posting supplies an explicit country
list. Timezone overlap is stored as a schedule constraint and does not by itself prove or deny
country eligibility.

Required regression examples:

| Posting evidence | Scope | Pakistan | Worldwide |
| --- | --- | --- | --- |
| `Remote` | unknown | unknown | no |
| `Worldwide` | worldwide | yes | yes |
| `You can work from anywhere within these regions: US and Europe` | region | no | no |
| `Remote — North America` | region | no | no |
| `Remote — APAC` without a country list | region | unknown | no |
| `Anywhere except US-sanctioned/restricted locations` | country_list | evaluate exclusions | no |
| Allowed countries include `PK` | country_list | yes | no |

Bump `TRUST_VERSION`, backfill every active canonical job, and save evidence for audit. The Linear
North America/Europe examples that exposed the defect must become explicit regression fixtures.

### Phase 6.3 — Refresh orchestration

Create a `DailyRefreshService` that coordinates existing components in this order:

1. Acquire the single-refresh lock and create a `refresh_runs` row.
2. Load enabled sources that are not inside an open circuit-breaker window.
3. Ingest sources with a configurable concurrency limit, initially `3`.
4. Continue when one source fails; record a partial-success state and preserve its last known jobs.
5. Never deactivate jobs from a source whose current run failed or returned an incomplete result.
6. Run eligibility v2 and canonical deduplication after all source attempts finish.
7. Rebuild matches once, using the current profile and the finalized canonical job set.
8. Persist the final counts and release the lock even after failure.

The operation must be idempotent. Repeated clicks on unchanged provider data must not create
duplicate postings, snapshots, or match rows. Retries reuse safe source behavior, circuit breakers,
timeouts, attribution requirements, and original application URLs.

Freshness rules remain strict:

- **Verified today:** provider publication timestamp is grade A/B and its Asia/Karachi date is
  today.
- **Newly discovered today:** first seen during the current refresh, but publication date may be
  unavailable or older.
- These counts and filters must never be merged or labeled as the same thing.

### Phase 6.4 — Matching integration

After ingestion, rebuild matches automatically against the unchanged current profile.

Hard-gate order:

1. active and canonical job
2. valid original/application link
3. `remote_mode=remote`
4. scope filter passes:
   - Worldwide view: `global_remote=true`
   - Pakistan view: `pakistan_eligibility=yes`
5. relevant role family and acceptable seniority
6. resume skill/domain/cloud constraints
7. deterministic score threshold

Increase `MATCHER_VERSION` because eligibility gates and evidence change. Do not let an old match
remain visible when its job becomes restricted, inactive, or non-canonical. Return whether each
visible match was newly created or materially changed by the selected refresh run.

### Phase 6.5 — Frontend refresh experience

Convert the refresh control into a small client component while keeping the match feed readable
and server-rendered where practical.

Add to `/matches`:

- **Fetch today's jobs** primary button
- disabled/running state that prevents duplicate clicks
- stages: Fetching sources → Checking eligibility → Ranking matches → Complete
- progress such as `8 of 26 sources checked`
- final summary cards for new, changed, verified today, worldwide, Pakistan-eligible, matched, and
  failed-source counts
- last successful refresh time in Asia/Karachi
- a retry action for failed sources after the first run has ended

Add clear filters/badges:

- **Worldwide only** — explicitly open from any country
- **Pakistan eligible** — Pakistan explicitly allowed, even if not worldwide
- **Eligibility unclear** — review queue, never included by default
- **Verified today** and **Newly discovered** as separate freshness filters
- **Region restricted** badge for excluded evidence views

Every match card should display work mode, geographic scope, Pakistan eligibility, freshness grade,
and concise inclusion evidence. Restricted jobs must not appear in strict ranked results.

The UI must survive refresh/reload by reading the latest run from the backend; progress cannot live
only in browser memory.

### Phase 6.6 — Verification and rollout

Unit tests:

- precedence of structured location and restriction phrases over generic remote wording
- worldwide, allowed-country, excluded-country, regional, authorization, and conflicting evidence
- Pakistan eligibility derivation and global-remote distinction
- Asia/Karachi verified-today versus newly-discovered behavior
- match hard gates after trust/matcher version changes

Service/integration tests:

- all-success, partial-failure, circuit-open, and no-profile refreshes
- concurrent-click locking and retry behavior
- unchanged rerun idempotency
- failed/incomplete source cannot close its previous jobs
- refresh completes ingestion before one match rebuild
- final counts reconcile with stored source runs, jobs, and matches

Frontend tests:

- button start, disabled, polling, success, partial-failure, and retry states
- correct filters and evidence badges
- page reload restores active/completed progress
- restricted North America/Europe job never appears in strict views

Live validation:

- validate one Greenhouse, Lever, Ashby, and Remote OK source
- manually audit a sample from every eligibility bucket against the original employer page
- record false-positive and false-negative findings before enabling strict results by default

## 6. Failure and safety behavior

- Use only registered HTTPS provider endpoints; the refresh request accepts no arbitrary URL.
- Keep existing retry limits, timeouts, circuit breakers, source attribution, and HTML sanitization.
- Do not expose internal exception traces or resume data in refresh responses/logs.
- One provider failure produces `completed_with_errors`, not a rollback of other successful sources.
- A total orchestration failure retains the last completed feed and matches.
- The UI must state when results may be stale because a source failed.

## 7. Acceptance criteria

Phase 6 is complete only when all of the following are true:

1. One click refreshes every eligible registered source and automatically rebuilds matches.
2. The user can observe progress and a durable final summary without using the terminal.
3. Duplicate clicks cannot create overlapping refreshes.
4. Repeating an unchanged refresh creates no duplicate jobs, snapshots, or match records.
5. `Remote` alone never qualifies a job as worldwide or Pakistan-eligible.
6. `Work from anywhere within this region` is classified as region-restricted.
7. North America/US/Europe-only roles are excluded from Pakistan and worldwide strict results.
8. Worldwide and Pakistan-eligible are separate filters with stored supporting evidence.
9. Resume role, seniority, skill, domain, work-mode, eligibility, freshness, and score constraints all
   run before a job becomes a visible match.
10. Verified-today and newly-discovered-today labels are accurate and separate.
11. Partial source failures are visible, auditable, retryable, and cannot delete last-known jobs.
12. Backend tests, frontend type checking/build, migrations, provider fixtures, and live sample audit
    pass with a written Phase 6 verification report.

## 8. Implementation order

1. Migration and API schemas.
2. Geographic eligibility classifier v2 plus regression fixtures.
3. Backfill command and trust-version bump.
4. Refresh orchestration, locking, progress APIs, and integration tests.
5. Matcher-version bump and refresh-to-match integration.
6. Frontend button, progress, result summaries, filters, and evidence display.
7. Full automated verification, four-provider live audit, and documentation update.

## 9. Official provider references

- Ashby exposes workplace type separately from location and country data:
  <https://developers.ashbyhq.com/docs/public-job-posting-api>
- Lever exposes `workplaceType`, `location`, `allLocations`, and country separately:
  <https://github.com/lever/postings-api>
- Greenhouse provides location and full posting content but no universal worldwide-eligibility
  flag: <https://docs.greenhouse.io/job-board.html>

These provider contracts are why Phase 6 must combine structured fields with evidence-preserving
description rules instead of equating `Remote` with `Worldwide`.
