type Source = {
  id: string;
  name: string;
  source_type: string;
  career_url: string | null;
  requires_attribution: boolean;
  attribution_name: string | null;
  attribution_url: string | null;
  health_status: string;
  last_job_count: number | null;
  last_checked_at: string | null;
};

type Health = {
  total: number;
  enabled: number;
  healthy: number;
  degraded: number;
  failing: number;
  unknown: number;
  circuits_open: number;
  sources: Source[];
};

async function getSourceHealth(): Promise<Health | null> {
  const baseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/sources/health`, { cache: "no-store" });
    return response.ok ? ((await response.json()) as Health) : null;
  } catch {
    return null;
  }
}

export default async function SourcesPage() {
  const health = await getSourceHealth();
  return (
    <main>
      <header className="adminHeader">
        <div>
          <p className="eyebrow">PHASE 3 ADMIN</p>
          <h1>Source health</h1>
        </div>
        <a href="/">Back to overview</a>
      </header>

      {!health ? (
        <section className="emptyState">
          <h2>Source API is offline</h2>
          <p>Start the backend, run migrations, and seed the Phase 3 registry.</p>
        </section>
      ) : (
        <>
          <section className="metricGrid" aria-label="Source health summary">
            <article className="metric"><strong>{health.total}</strong><span>Total sources</span></article>
            <article className="metric"><strong>{health.enabled}</strong><span>Enabled</span></article>
            <article className="metric"><strong>{health.healthy}</strong><span>Healthy</span></article>
            <article className="metric"><strong>{health.degraded}</strong><span>Degraded</span></article>
            <article className="metric"><strong>{health.failing}</strong><span>Failing</span></article>
            <article className="metric"><strong>{health.unknown}</strong><span>Not checked</span></article>
            <article className="metric"><strong>{health.circuits_open}</strong><span>Circuits open</span></article>
          </section>
          <div className="tableWrap">
            <table className="sourceTable">
              <thead><tr><th>Source</th><th>Provider</th><th>Health</th><th>Jobs</th><th>Checked</th></tr></thead>
              <tbody>
                {health.sources.map((source) => {
                  const link = source.requires_attribution
                    ? source.attribution_url
                    : source.career_url;
                  const label = source.requires_attribution
                    ? `Source: ${source.attribution_name}`
                    : source.name;
                  return (
                    <tr key={source.id}>
                      <td>{link ? <a href={link}>{label}</a> : label}</td>
                      <td>{source.source_type}</td>
                      <td className={source.health_status === "healthy" ? "healthHealthy" : "healthOther"}>{source.health_status}</td>
                      <td>{source.last_job_count ?? "—"}</td>
                      <td>{source.last_checked_at ? new Date(source.last_checked_at).toLocaleString() : "Never"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
