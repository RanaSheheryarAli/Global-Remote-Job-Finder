# Phase 5 verification - 2026-09-04

## Automated checks

- Backend lint: passed.
- Backend tests: 31 passed.
- Matching fixtures: stable known-good score, unknown-eligibility opt-in, explicit ineligibility,
  unrelated-role exclusion, entry-level exclusion, private resume facts, and invalid-PDF rejection.
- Frontend production build and TypeScript validation: passed.
- Alembic revision: `20260904_0004`.

## Resume integrity and privacy

- A private local PDF was used for end-to-end parser verification and was not committed.
- Personal identifiers, contact details, raw document bytes, hashes, and extracted profile values
  are intentionally omitted from this public report.
- Contact values retained in candidate-profile fields: 0.
- Raw PDF bytes and full resume text stored in matching tables: no.

## Current profile

- Private profile extraction completed successfully.
- Parsed profile values are intentionally omitted from this public report.

## Live scoring

- Active canonical jobs were scored against the private local profile.
- Repeat rebuilds produced stable results without duplicate match rows.
- Explicitly Pakistan-ineligible jobs with a positive score: 0.
- Invalid strict results (not remote or not Pakistan Yes): 0.

## Live surfaces

- Candidate profile: HTTP 200 at `/profile`.
- Ranked matches: HTTP 200 at `/matches`.
- FastAPI health: phase `1-5`.
- Backend, frontend, and PostgreSQL containers: running; PostgreSQL healthy.
