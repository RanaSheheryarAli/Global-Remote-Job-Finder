# Global Remote Job Discovery Tool

A private, API-first application that discovers remote jobs, preserves source evidence, and ultimately matches verified opportunities against an unchanged resume.

## Implemented phases

- **Phase 1 - Engineering foundation:** FastAPI backend, Next.js frontend, PostgreSQL models, Alembic migration, Docker Compose, configuration, health endpoints, tests, and CI.
- **Phase 2 - Greenhouse reference ingestion:** public Greenhouse adapter, per-job detail retrieval, `first_published` capture, retries, normalized records, immutable content snapshots, source-run metrics, missing-job deactivation, API endpoints, and unit fixtures.
- **Phase 3 - Source expansion and registry:** Lever, Ashby, and Remote OK adapters; provider-aware source validation; original/apply URL preservation; workplace, employment, compensation, and attribution fields; source health, circuit breakers, a 25-company live-validated registry, and a basic admin source-health page.
- **Phase 4 - Trust layer:** normalized fields, Asia/Karachi freshness grades, separate remote-mode and Pakistan-eligibility classifiers with evidence, distinct Gulf employer/location facts, cross-source canonical deduplication, repost detection, closure history, trusted-job APIs, and a filterable frontend feed.
- **Phase 5 - Resume profile and matching:** privacy-minimized PDF parsing, immutable profile versions, a technology synonym ontology, role/seniority/domain extraction, hard eligibility gates, deterministic 100-point scoring, matched/missing skills, evidence, ranked-match APIs, and profile/match screens.

Phases 6 and 7 remain intentionally deferred: the complete application workflow dashboard,
persistent job actions, and notifications/private-launch operations.

## Repository structure

```text
backend/       FastAPI, SQLAlchemy, Alembic, ingestion services, tests
frontend/      Next.js overview, trusted-jobs feed, and source-health screen
docs/          Architecture and phase notes
.github/       Continuous integration workflow
docker-compose.yml
```

## Quick start with Docker

1. Copy `.env.example` to `.env`.
2. Start the stack:

   ```bash
   docker compose up --build
   ```

3. Run the migration:

   ```bash
   docker compose exec backend alembic upgrade head
   ```

4. Seed the validated Phase 3 registry:

   ```bash
   curl -X POST http://localhost:8000/api/v1/sources/seed/phase-3
   ```

5. Open:

   - Frontend: <http://localhost:3000>
   - API docs: <http://localhost:8000/docs>
   - API health: <http://localhost:8000/api/v1/health>
   - Trusted jobs: <http://localhost:3000/jobs>
   - Ranked matches: <http://localhost:3000/matches>
   - Candidate profile: <http://localhost:3000/profile>
   - Source health: <http://localhost:3000/sources>

## Local backend development

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Local frontend development

```bash
cd frontend
npm install
npm run dev
```

## Add and ingest a source

Create a source:

```bash
curl -X POST http://localhost:8000/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{"name":"Example Company","source_type":"greenhouse","board_token":"examplecompany"}'
```

Then run ingestion with the returned source ID:

```bash
curl -X POST http://localhost:8000/api/v1/sources/SOURCE_ID/ingest
```

Supported `source_type` values are `greenhouse`, `lever`, `ashby`, and `remoteok`.
Public job reads do not require an applicant-owned API key. This project never requests or
stores an employer application key.

## Validate all Phase 3 definitions live

The validator uses Node's built-in `fetch`, so it needs no npm installation:

```bash
node scripts/validate_phase3_sources.mjs
```

Remote OK records retain visible source attribution and link back to the Remote OK listing.

## Trusted jobs API

`GET /api/v1/jobs` returns active canonical jobs classified by trust version. Supported filters
include `strict_today`, `eligibility`, `remote_mode`, `freshness_grade`, `gulf_employer`,
`gulf_location`, and `q`. `GET /api/v1/jobs/trust/summary` returns feed-level counts.

Strict today means a grade A/B publication timestamp that falls on the current Asia/Karachi
calendar date, plus remote mode and explicit Pakistan eligibility. A first-seen timestamp never
qualifies a job for this filter.

## Resume and matching API

`POST /api/v1/resume?filename=resume.pdf` accepts a raw `application/pdf` body up to 2 MB and
creates a private structured profile version. Raw resume text, email, and phone are not stored in
the matching tables. `GET /api/v1/profile` returns the current reviewable facts.

`POST /api/v1/matches/rebuild` deterministically scores all active canonical trusted jobs.
`GET /api/v1/matches` returns strict matches by default; `include_uncertain=true` adds jobs whose
Pakistan eligibility needs review. The matcher uses the plan's 35/20/15/15/10/5 component weights
and never uses generative output for the numeric score.

The latest completed-phase verification is recorded in
[`docs/test-report-phase5-2026-09-04.md`](docs/test-report-phase5-2026-09-04.md).
