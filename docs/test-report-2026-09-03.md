# Test report - completed Phases 1 through 3

Tested on **2026-09-03** from Windows with Docker Desktop, Python 3.12 containers,
Node.js 22 containers, and PostgreSQL 16.

## Passed checks

- Python compilation completed for every backend module.
- All project JSON files parsed successfully.
- The Phase 3 registry passed its Pydantic schema rules: 26 definitions, 25 company
  boards, four provider types, and two Gulf employers (Careem and Tamara).
- Negative schema checks correctly rejected an unsafe provider identifier, invalid company
  domain, unsupported provider region, and missing Remote OK attribution.
- Database migration fields matched the SQLAlchemy job and source models.
- Docker Compose service definitions and the admin health-screen contract were present.
- The source-health state machine passed degraded, failing, circuit-open, and recovery
  scenarios.
- Twelve offline runtime checks passed against production adapter and ingestion-service code:
  Greenhouse detail normalization and identifier safety; Lever URLs and compensation; Ashby
  filtering and fields; Remote OK attribution and legal guard; stable hashing; and the new,
  unchanged, changed, snapshot, timestamp-recheck, and failure ingestion paths.
- The dependency-free Node.js validator syntax passed.
- Live provider validation passed **26 of 26** configured sources. Every source returned at
  least one current job and a valid original HTTPS job URL.
- The standard backend suite passed **14 of 14** pytest tests, and Ruff passed with no findings.
- The Next.js optimized production build, lint step, and TypeScript validity check passed.
- Docker Compose successfully built and started PostgreSQL, the FastAPI backend, and the Next.js
  frontend. PostgreSQL reported healthy and all application containers remained running.
- Alembic upgraded a clean database through both migrations and reported revision
  `20260903_0002 (head)`.
- Registry seeding created 26 sources and a second seed created zero duplicates.
- Live validation through the running backend passed all 26 registered sources: 26 healthy,
  zero degraded, zero failing, and zero unchecked.
- Representative ingestion stored 150 active postings with 150 initial snapshots. A second run
  produced 150 unchanged records, zero new records, zero changes, and zero deactivations.
- The backend health API, source-health API, frontend home page, frontend source page, and API
  documentation all returned HTTP 200.

No defect remains from the executed test scope. The stack was left running locally after the
final verification.
