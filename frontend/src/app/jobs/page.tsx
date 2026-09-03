type Job = {
  id: string;
  source_name: string;
  source_type: string;
  employer_name: string;
  title: string;
  location_text: string | null;
  description_excerpt: string;
  source_url: string;
  application_url: string;
  normalized_employment_type: string | null;
  normalized_compensation: {
    min?: number | null;
    max?: number | null;
    currency?: string | null;
    interval?: string | null;
    summary?: string | null;
  } | null;
  attribution_name: string | null;
  attribution_url: string | null;
  first_published_at: string | null;
  last_verified_at: string | null;
  freshness_grade: "A" | "B" | "C" | "D";
  freshness_label: string;
  published_local_date: string | null;
  is_reposted: boolean;
  remote_mode: "remote" | "hybrid" | "onsite" | "unknown";
  pakistan_eligibility: "yes" | "no" | "unknown";
  eligibility_positive_evidence: string[];
  eligibility_negative_evidence: string[];
  employer_headquarters_gcc: boolean;
  job_location_gcc: boolean | null;
};

type JobList = {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
  strict_today: boolean;
  timezone: string;
};

type TrustSummary = {
  local_date: string;
  timezone: string;
  trusted_active: number;
  canonical_active: number;
  strict_today: number;
  pakistan_yes: number;
  pakistan_unknown: number;
  freshness: Record<string, number>;
};

const filters = [
  { key: "all", label: "All trusted", query: "" },
  { key: "today", label: "Strict today", query: "strict_today=true" },
  { key: "eligible", label: "Pakistan eligible", query: "eligibility=yes" },
  { key: "unclear", label: "Eligibility unclear", query: "eligibility=unknown" },
  { key: "gulf", label: "Gulf employers", query: "gulf_employer=true" },
];

async function getData(mode: string): Promise<{
  jobs: JobList | null;
  summary: TrustSummary | null;
}> {
  const baseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";
  const selected = filters.find((filter) => filter.key === mode) ?? filters[0];
  const suffix = selected.query ? `?${selected.query}` : "";
  try {
    const [jobsResponse, summaryResponse] = await Promise.all([
      fetch(`${baseUrl}/api/v1/jobs${suffix}`, { cache: "no-store" }),
      fetch(`${baseUrl}/api/v1/jobs/trust/summary`, { cache: "no-store" }),
    ]);
    return {
      jobs: jobsResponse.ok ? ((await jobsResponse.json()) as JobList) : null,
      summary: summaryResponse.ok ? ((await summaryResponse.json()) as TrustSummary) : null,
    };
  } catch {
    return { jobs: null, summary: null };
  }
}

function compensation(job: Job): string | null {
  const value = job.normalized_compensation;
  if (!value) return null;
  if (value.summary) return value.summary;
  if (value.min == null && value.max == null) return null;
  const currency = value.currency ? `${value.currency} ` : "";
  const range = value.min === value.max || value.max == null
    ? value.min
    : `${value.min ?? "?"}–${value.max}`;
  return `${currency}${range}${value.interval ? ` / ${value.interval}` : ""}`;
}

export default async function JobsPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string }>;
}) {
  const mode = (await searchParams).mode ?? "all";
  const { jobs, summary } = await getData(mode);
  return (
    <main>
      <header className="adminHeader jobsHeader">
        <div>
          <p className="eyebrow">PHASE 4 TRUST LAYER</p>
          <h1>Trusted jobs</h1>
          <p className="lead jobsLead">
            Freshness, remote mode, Pakistan eligibility and Gulf context are kept separate.
          </p>
        </div>
        <nav className="headerNav"><a href="/matches">Ranked matches</a><a href="/">Overview</a></nav>
      </header>

      {!jobs || !summary ? (
        <section className="emptyState">
          <h2>Jobs API is offline</h2>
          <p>Start the backend and apply the latest database migration.</p>
        </section>
      ) : (
        <>
          <section className="metricGrid trustMetrics" aria-label="Trust summary">
            <article className="metric"><strong>{summary.canonical_active}</strong><span>Unique active jobs</span></article>
            <article className="metric"><strong>{summary.strict_today}</strong><span>Strict today</span></article>
            <article className="metric"><strong>{summary.pakistan_yes}</strong><span>Pakistan eligible</span></article>
            <article className="metric"><strong>{summary.pakistan_unknown}</strong><span>Needs eligibility review</span></article>
          </section>

          <nav className="filterBar" aria-label="Job filters">
            {filters.map((filter) => (
              <a
                className={filter.key === mode ? "filterActive" : ""}
                href={filter.key === "all" ? "/jobs" : `/jobs?mode=${filter.key}`}
                key={filter.key}
              >
                {filter.label}
              </a>
            ))}
          </nav>

          <div className="feedMeta">
            <strong>{jobs.total} result{jobs.total === 1 ? "" : "s"}</strong>
            <span>Today means {summary.local_date} in {summary.timezone}</span>
          </div>

          {jobs.items.length === 0 ? (
            <section className="emptyState">
              <h2>No jobs meet this filter</h2>
              <p>The strict filter never treats the time first discovered as a publication date.</p>
            </section>
          ) : (
            <section className="jobFeed" aria-label="Trusted job results">
              {jobs.items.map((job) => {
                const salary = compensation(job);
                return (
                  <article className="jobCard" key={job.id}>
                    <div className="jobCardTop">
                      <div>
                        <p className="jobCompany">{job.employer_name}</p>
                        <h2>{job.title}</h2>
                      </div>
                      <span className={`grade grade${job.freshness_grade}`} title={job.freshness_label}>
                        Freshness {job.freshness_grade}
                      </span>
                    </div>
                    <div className="badgeRow">
                      <span>{job.remote_mode}</span>
                      <span className={`eligibility eligibility${job.pakistan_eligibility}`}>
                        Pakistan: {job.pakistan_eligibility}
                      </span>
                      {job.employer_headquarters_gcc && <span>Gulf employer</span>}
                      {job.job_location_gcc && <span>Gulf location</span>}
                      {job.is_reposted && <span>Reposted</span>}
                    </div>
                    <p className="jobLocation">{job.location_text ?? "Location not stated"}</p>
                    {salary && <p className="jobSalary">{salary}</p>}
                    <p className="jobExcerpt">{job.description_excerpt}</p>
                    {(job.eligibility_positive_evidence.length > 0 || job.eligibility_negative_evidence.length > 0) && (
                      <div className="evidence">
                        <strong>Eligibility evidence</strong>
                        {[...job.eligibility_positive_evidence, ...job.eligibility_negative_evidence]
                          .slice(0, 2)
                          .map((item) => <p key={item}>“{item}”</p>)}
                      </div>
                    )}
                    <footer className="jobFooter">
                      <div>
                        <span>{job.source_name} · {job.source_type}</span>
                        <span>{job.published_local_date ? `Published ${job.published_local_date}` : job.freshness_label}</span>
                      </div>
                      <div className="jobLinks">
                        <a href={job.source_url} rel="noopener noreferrer" target="_blank">Evidence</a>
                        <a className="applyLink" href={job.application_url} rel="noopener noreferrer" target="_blank">Apply</a>
                      </div>
                    </footer>
                    {job.attribution_name && job.attribution_url && (
                      <a className="attribution" href={job.attribution_url} rel="noopener noreferrer" target="_blank">
                        Source: {job.attribution_name}
                      </a>
                    )}
                  </article>
                );
              })}
            </section>
          )}
        </>
      )}
    </main>
  );
}
