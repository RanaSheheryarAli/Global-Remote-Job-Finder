# Phase 8 - Matcher V3, company diversity, sources, and resume upload

## Goal

Improve the quality of ranked results before increasing their volume. A job must first be a
relevant remote software role and pass geographic eligibility. Matcher V3 then compares explicit
requirements, responsibility themes, role family, skill depth, seniority, and technical context
against the current resume profile.

## Resume replacement workflow

The **My profile** screen accepts a PDF resume up to 2 MB. Uploading creates a new immutable
candidate-profile version; it never overwrites an older profile. The browser then requests a full
match rebuild for the new current version and refreshes the profile screen. Raw PDF bytes, raw
resume text, email addresses, and phone numbers are not stored in matching tables.

## Matcher V3

The deterministic 100-point score is:

| Component | Points |
| --- | ---: |
| Explicit required or inferred skills | 30 |
| Responsibility alignment | 25 |
| Target role/title alignment | 15 |
| Resume skill depth | 15 |
| Seniority alignment | 10 |
| Architecture, cloud, and domain context | 5 |

The parser separates required and preferred sections, recognizes title-critical technologies,
extracts minimum years, and classifies responsibility themes. Inactive, non-canonical,
non-remote, irrelevant, entry-level, explicitly Pakistan-ineligible, title-technology-mismatched,
low required-skill-coverage, and experience-shortfall jobs are blocked before scoring.

Visible matches start at 68 points. Scores from 68 through 79 are **Review** and scores of 80 or
more are **Apply ready**. Freshness and the word `remote` do not add points that could hide a weak
technical match; they remain separate trust and eligibility gates.

## Company diversity

Ranked results show the highest-scoring role per normalized company by default. This prevents a
large employer from filling the first page and encourages a sensible application spread. The UI
can switch to all roles, and the API exposes `company_limit=1` by default or `company_limit=0` for
unlimited roles. Pagination and totals are calculated after this diversity rule.

## Source coverage

The source registry now contains 28 direct company boards and five attributed public feeds.
SmartRecruiters is supported through its public Posting API, initially adding Software Mind, Cint,
and ServiceNow. Himalayas queries are targeted at both worldwide roles and Pakistan-eligible roles;
Jobicy requests worldwide engineering jobs explicitly. Existing relevance filtering still runs
before persistence, so expanding sources does not knowingly store unrelated roles.

No Google Jobs scraper is included. Google Jobs is a search presentation layer without a supported
public job-search API for this use case; brittle result-page scraping would add avoidable policy,
maintenance, and data-quality risk.

## Deployment

Alembic revision `20260909_0007` expands the provider constraint, adds the company-ranking index,
and inserts the three initial SmartRecruiters sources. Render must continue to run
`alembic upgrade head` during deployment. No new environment variable or provider API key is
required for this phase.

## Acceptance checks

- A valid PDF can be uploaded from **My profile**, creates a new profile version, and triggers a
  deterministic rebuild.
- A title-critical technology or minimum-experience mismatch is excluded with an evidence reason.
- One company contributes at most one visible ranked match by default.
- Selecting **Show all company roles** removes the company cap while retaining pagination.
- SmartRecruiters, Himalayas, and Jobicy normalize into the same relevance, trust, and matching
  pipeline as existing providers.
- Backend tests and lint, frontend type-check, production build, and the Alembic upgrade pass.
