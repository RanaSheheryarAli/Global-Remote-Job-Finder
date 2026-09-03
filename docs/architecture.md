# Architecture notes - Phases 1 through 5

## Boundary

The backend uses five explicit ingestion boundaries:

1. **Source adapter** retrieves provider-specific public data.
2. **Normalizer** converts provider records into canonical job fields.
3. **Ingestion service** decides whether details and snapshots are required.
4. **Trust engine** classifies normalized records using deterministic, evidence-preserving rules.
5. **Repository** persists sources, runs, canonical postings, and immutable snapshots.

The service depends on protocols rather than SQLAlchemy or HTTP directly. Unit tests therefore run with fake adapters and repositories.

## Greenhouse behavior

- The list endpoint is fetched first.
- New or source-updated jobs receive a detail request.
- `first_published` is captured from the detail payload.
- A canonical SHA-256 hash is calculated from material fields and raw source data.
- A snapshot is stored only when that hash is new.
- Existing unchanged jobs only update `last_seen_active_at`.
- Jobs absent from a successful complete board response are marked inactive.
- Retry is limited to transient HTTP/network failures.
- A successful run commits atomically; a failed run rolls back partial job changes and keeps only
  a failure audit record.

## Data ownership

- `source_registry` owns the company/board configuration.
- `source_runs` records collection metrics.
- `job_postings` stores the current canonical state.
- `job_snapshots` stores immutable historical source states.

## Phase 3 provider behavior

- **Lever:** paginated public Postings API; no public publication timestamp is treated as
  authoritative, so records remain first-seen freshness only.
- **Ashby:** public job board endpoint with `publishedAt`, listed-only filtering, workplace,
  employment type, compensation, hosted job URL, and apply URL.
- **Remote OK:** public JSON feed with its legal metadata checked on every run. Records retain
  visible `Remote OK` attribution and a followed link to the Remote OK listing.
- **Greenhouse:** remains the reference adapter and only performs a detail request when its
  list-level update timestamp indicates one is needed.

All adapters keep provider-specific retrieval behind the same summary/normalization contract.
Ashby and Remote OK normalize every in-memory list record so content edits cannot be missed when
their publication timestamp is unchanged; this creates no additional HTTP request.

## Source registry and health

The Phase 3 seed contains 25 company boards plus one Remote OK aggregator definition. Source
configuration is validated by provider type, identifier, company name, domain, region, and
attribution requirements. Successful validation records a sample original URL. Consecutive
failures move a source from degraded to failing and open a configurable cooldown circuit.

## Phase 4 trust behavior

- Original title, description, location, source URL, apply URL, and snapshots remain unchanged;
  comparable normalized fields are stored beside them.
- Freshness A is an official Greenhouse/Ashby publication timestamp, B is a Remote OK feed
  timestamp, C is Lever first discovery without an authoritative publication timestamp, and D is
  unverified. Verified times are also stored as an Asia/Karachi calendar date.
- Strict today requires grade A/B, today's Asia/Karachi date, remote mode, and explicit Pakistan
  eligibility. `first_seen_at` is never used as a substitute publication date.
- Remote/hybrid/on-site classification and Pakistan eligibility are independent. Positive and
  negative evidence snippets are stored; conflicting evidence remains `unknown`.
- Gulf employer headquarters and Gulf job location are separate Boolean facts and do not imply
  Pakistan eligibility.
- Provider ID deduplication remains authoritative within a source. Cross-source candidates require
  a stable employer/title/location key plus exact or high-similarity description evidence. A
  canonical family preserves every provider record and original URL.
- Missing jobs are closed only after a successful complete source response. Their timestamps and
  snapshots remain available, and an active duplicate can be promoted as the canonical record.
- HTML descriptions are allowlist-sanitized before any later UI rendering.

## Deferred decisions

The complete application workflow dashboard and persistent job actions belong to Phase 6. Alerts,
authentication hardening, backups, and private-launch operations belong to Phase 7.

## Phase 5 resume and matching behavior

- The resume endpoint accepts only a bounded PDF body and creates an immutable candidate-profile
  version. It stores the source filename and SHA-256 plus normalized career facts; raw PDF bytes,
  full extracted text, email, and phone are not stored in matching tables.
- Extraction records role families, seniority, normalized skills, cloud platforms, domains,
  experience duration, preferences, and limited non-contact evidence for review.
- The ontology resolves common equivalents such as Node/Node.js, Postgres/PostgreSQL,
  Google Cloud/GCP, and LLM/RAG terms into stable canonical names.
- Hard gates run before scoring. Inactive/non-canonical, missing-link, non-remote, irrelevant,
  entry-level/internship, and explicitly Pakistan-ineligible jobs cannot become visible matches.
  Unknown eligibility is excluded by default and can be opted into separately.
- The reproducible score follows the approved weights: required/core skills 35, role/title 20,
  seniority/leadership 15, architecture/cloud/domain 15, work arrangement 10, and freshness 5.
- Every match stores component values, matched skills, missing skills, gate reasons, and a
  deterministic evidence explanation. The matcher version participates in uniqueness so a later
  scoring revision cannot silently overwrite earlier evaluation history.
- A profile version owns its match records. Rebuilding the same profile/matcher version updates
  those records idempotently instead of creating duplicate scores.
