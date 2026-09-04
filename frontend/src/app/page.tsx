type Health = { status: string; phase: string };

async function getHealth(): Promise<Health | null> {
  const baseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${baseUrl}/api/v1/health`, { cache: "no-store" });
    return response.ok ? ((await response.json()) as Health) : null;
  } catch {
    return null;
  }
}

const phases = [
  {
    name: "Phase 1",
    title: "Engineering foundation",
    state: "Implemented",
    details: "FastAPI, Next.js, PostgreSQL, Alembic, configuration, Docker, tests and CI.",
  },
  {
    name: "Phase 2",
    title: "Greenhouse ingestion",
    state: "Implemented",
    details: "Public board adapter, publication timestamps, snapshots, retries and source runs.",
  },
  {
    name: "Phase 3",
    title: "Source expansion and registry",
    state: "Implemented",
    details: "Lever, Ashby, Remote OK, source validation, health tracking and 25 companies.",
  },
  {
    name: "Phase 4",
    title: "Trust layer",
    state: "Implemented",
    details: "Freshness grades, Pakistan eligibility evidence, Gulf facts, deduplication and trusted feed.",
  },
  {
    name: "Phase 5",
    title: "Resume and matching",
    state: "Implemented",
    details: "Private versioned profile, skill ontology, hard gates, transparent scores and match evidence.",
  },
  {
    name: "Phase 6",
    title: "Daily refresh and global matching",
    state: "Implemented",
    details: "One-click source refresh, strict geographic eligibility, progress and automatic ranking.",
  },
];

export default async function Home() {
  const health = await getHealth();
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">PRIVATE JOB DISCOVERY</p>
        <h1>Global Remote Job Tool</h1>
        <p className="lead">
          Evidence-first ingestion for fresh remote jobs, built phase by phase.
        </p>
        <div className={health ? "status statusOk" : "status statusOffline"}>
          <span aria-hidden="true" />
          {health ? `API online · phases ${health.phase}` : "API offline · start the backend"}
        </div>
      </section>

      <section className="phaseGrid" aria-label="Implementation phases">
        {phases.map((phase) => (
          <article className="card" key={phase.name}>
            <div className="cardHeader">
              <p>{phase.name}</p>
              <span className={phase.state === "Implemented" ? "done" : "planned"}>
                {phase.state}
              </span>
            </div>
            <h2>{phase.title}</h2>
            <p>{phase.details}</p>
          </article>
        ))}
      </section>

      <section className="nextStep">
        <div>
          <p className="eyebrow">AVAILABLE NOW</p>
          <h2>Fetch today's jobs and review globally eligible resume matches.</h2>
        </div>
        <div className="actions">
          <a href="/matches">Ranked matches</a>
          <a href="/profile">Candidate profile</a>
          <a href="/jobs">Trusted jobs</a>
          <a href="/sources">Source health</a>
          <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/docs`}>
            API documentation
          </a>
        </div>
      </section>
    </main>
  );
}
