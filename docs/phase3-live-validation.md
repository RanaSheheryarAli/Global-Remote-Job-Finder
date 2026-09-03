# Phase 3 live source validation

Validated at **2026-09-03 17:22 UTC** with `scripts/validate_phase3_sources.mjs`.
All 25 company boards and the Remote OK aggregator returned a successful public response,
at least one published job, and an HTTPS original listing URL.

| Source | Provider | Jobs at validation | Registry category |
|---|---:|---:|---|
| GitLab | Greenhouse | 228 | Remote-first technology |
| Cloudflare | Greenhouse | 326 | Technology |
| Datadog | Greenhouse | 443 | Technology |
| MongoDB | Greenhouse | 407 | Technology |
| Grafana Labs | Greenhouse | 134 | Remote-first technology |
| Canonical | Greenhouse | 302 | Remote-first technology |
| Coinbase | Greenhouse | 186 | Remote-first technology |
| Affirm | Greenhouse | 203 | Technology |
| Okta | Greenhouse | 323 | Technology |
| Dropbox | Greenhouse | 40 | Remote-first technology |
| Elastic | Greenhouse | 358 | Remote-first technology |
| Figma | Greenhouse | 157 | Technology |
| Airtable | Greenhouse | 16 | Technology |
| Stripe | Greenhouse | 603 | Technology |
| Careem | Greenhouse | 19 | Gulf technology employer (UAE) |
| Tamara | Greenhouse | 33 | Gulf technology employer (Saudi Arabia) |
| Ashby | Ashby | 65 | Remote-first technology |
| Linear | Ashby | 28 | Remote-first technology |
| OpenAI | Ashby | 765 | Technology |
| Supabase | Ashby | 61 | Remote-first technology |
| Appen | Lever | 31 | Distributed AI/data services |
| Xsolla | Lever | 176 | Distributed technology |
| JumpCloud | Lever | 17 | Remote-first technology |
| Getty Images | Lever | 11 | Distributed technology |
| Corbalt | Lever | 3 | Remote-first technology |
| Remote OK | Remote OK | 100 | Aggregator; attribution required |

Job counts are point-in-time health evidence, not fixed expectations. Future validation succeeds
when the source responds, contains at least one published job, and exposes a valid original HTTPS
URL.

## Provider rules encoded by the implementation

- [Lever Postings API](https://github.com/lever/postings-api): public GET endpoints use the
  company site identifier and preserve both `hostedUrl` and `applyUrl`. The undocumented
  `createdAt` value is not presented as an authoritative publication time.
- [Ashby public Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api):
  requests include compensation, exclude `isListed: false`, and preserve `publishedAt`, workplace,
  employment type, compensation, job URL, and apply URL.
- [Remote OK JSON API](https://remoteok.com/api): the legal metadata is checked on every fetch.
  Stored records require visible “Remote OK” attribution and a followed link to the Remote OK URL.
- Greenhouse remains the reference provider, with job-detail requests used for authoritative
  `first_published` and canonical URLs.
