# Phase 6 verification report — 2026-09-04

## Result

Phase 6 passed its local automated, live-provider, API, database, and browser verification.

## Automated checks

- Backend lint: passed (`ruff check app tests`).
- Backend tests: 42 passed.
- Frontend production build: passed, including lint and TypeScript validation.
- Alembic migration `20260904_0005_daily_refresh_global_scope`: applied successfully.
- Docker services: backend and frontend running; PostgreSQL healthy.

## Live refresh verification

Final refresh run: `edc94d12-1bd2-40fc-8809-b93c2713e81c`.

- Status: completed.
- Sources: 26 of 26 succeeded; 0 failed.
- Jobs received: 5,052.
- Newly discovered: 2.
- Unchanged: 5,050.
- Verified publication date today: 41.
- Explicit worldwide eligibility: 116.
- Explicit Pakistan eligibility: 124.
- Eligibility unclear: 154.
- Jobs scored against the current resume: 4,977.
- Strict visible matches: 20.
- Unclear visible matches: 7.

An earlier run intentionally exercised partial-failure reporting when Appen returned an
overlong employment label. The label normalization was corrected, and Appen passed in both
subsequent all-source runs.

## Geographic eligibility regressions

- A Linear role labelled `North America` remains remote work mode but is classified as not
  Pakistan-eligible and not worldwide.
- Europe and US/country-only roles are excluded from strict Pakistan and worldwide results.
- `Remote` without geographic permission remains unclear, never worldwide by assumption.
- Poland, Americas, city-only, hybrid, and office-labelled postings cannot become worldwide
  merely because their company description mentions worldwide customers, compensation, or
  benefits.
- After the trust-version backfill, every active worldwide record has an explicit provider
  location label: `Home based - Worldwide` (82) or `Remote, Global` (34).

## API and browser checks

- Pakistan, worldwide, unclear, verified-today, and newly-discovered refresh filters returned
  valid responses.
- The `/matches` screen visibly displayed the Phase 6 heading, refresh button, 26/26 completion,
  counters, all eligibility/freshness filters, location evidence, and ranked results.
- The final visible match totals were 20 Pakistan-eligible, 20 worldwide, and 7 unclear.
- Zero verified-today or newly-discovered jobs met every resume score and eligibility gate in
  this run; the feed counters and match counters correctly remain separate.

