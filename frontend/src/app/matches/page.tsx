type Match = {
  id: string;
  profile_version: number;
  matcher_version: number;
  hard_gate_passed: boolean;
  uncertain_gate_passed: boolean;
  gate_reasons: string[];
  score: number;
  score_label: string;
  components: Record<string, number>;
  matched_skills: string[];
  missing_skills: string[];
  evidence: { explanation?: string; gulf_preference_applied?: boolean };
  job: {
    id: string;
    employer_name: string;
    title: string;
    location_text: string | null;
    source_name: string;
    source_type: string;
    source_url: string;
    application_url: string;
    freshness_grade: string;
    freshness_label: string;
    published_local_date: string | null;
    pakistan_eligibility: string;
    employer_headquarters_gcc: boolean;
  };
};

type MatchList = {
  items: Match[];
  total: number;
  include_uncertain: boolean;
  min_score: number;
};

const componentWeights: Record<string, number> = {
  required_core_skills: 35,
  role_title: 20,
  seniority_leadership: 15,
  architecture_cloud_domain: 15,
  work_arrangement: 10,
  freshness: 5,
};

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

async function getMatches(includeUncertain: boolean): Promise<MatchList | null> {
  const baseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(
      `${baseUrl}/api/v1/matches?include_uncertain=${includeUncertain}`,
      { cache: "no-store" },
    );
    return response.ok ? ((await response.json()) as MatchList) : null;
  } catch {
    return null;
  }
}

export default async function MatchesPage({
  searchParams,
}: {
  searchParams: Promise<{ eligibility?: string }>;
}) {
  const includeUncertain = (await searchParams).eligibility === "uncertain";
  const matches = await getMatches(includeUncertain);
  return (
    <main>
      <header className="adminHeader jobsHeader">
        <div>
          <p className="eyebrow">PHASE 5 · REPRODUCIBLE RANKING</p>
          <h1>Ranked matches</h1>
          <p className="lead jobsLead">
            Hard gates run first. Every visible score is a transparent 100-point calculation.
          </p>
        </div>
        <nav className="headerNav"><a href="/profile">Candidate profile</a><a href="/jobs">Trusted jobs</a></nav>
      </header>

      {!matches ? (
        <section className="emptyState"><h2>Matches are not ready</h2><p>Create a profile and rebuild matches.</p></section>
      ) : (
        <>
          <nav className="filterBar" aria-label="Eligibility filter">
            <a className={!includeUncertain ? "filterActive" : ""} href="/matches">Strictly eligible</a>
            <a className={includeUncertain ? "filterActive" : ""} href="/matches?eligibility=uncertain">Include unclear</a>
          </nav>
          <div className="feedMeta">
            <strong>{matches.total} match{matches.total === 1 ? "" : "es"} scoring {matches.min_score}+</strong>
            <span>{includeUncertain ? "Pakistan Yes + Unknown" : "Pakistan eligibility Yes only"}</span>
          </div>
          {matches.items.length === 0 ? (
            <section className="emptyState"><h2>No visible matches</h2><p>Hard gates or the minimum score removed the current jobs.</p></section>
          ) : (
            <section className="jobFeed" aria-label="Ranked job matches">
              {matches.items.map((match) => (
                <article className="jobCard matchCard" key={match.id}>
                  <div className="jobCardTop">
                    <div>
                      <p className="jobCompany">{match.job.employer_name}</p>
                      <h2>{match.job.title}</h2>
                    </div>
                    <div className="scoreBadge"><strong>{match.score}</strong><span>{match.score_label}</span></div>
                  </div>
                  <div className="badgeRow">
                    <span className={`eligibility eligibility${match.job.pakistan_eligibility}`}>
                      Pakistan: {match.job.pakistan_eligibility}
                    </span>
                    <span>Freshness {match.job.freshness_grade}</span>
                    {match.job.employer_headquarters_gcc && <span>Gulf employer</span>}
                  </div>
                  <p className="jobLocation">{match.job.location_text ?? "Location not stated"}</p>
                  {match.evidence.explanation && <p className="matchExplanation">{match.evidence.explanation}</p>}
                  {match.gate_reasons.length > 0 && (
                    <p className="uncertaintyNote">{match.gate_reasons.join(" · ")}</p>
                  )}
                  <div className="scoreGrid">
                    {Object.entries(match.components).map(([name, value]) => (
                      <div className="scoreRow" key={name}>
                        <div><span>{humanize(name)}</span><strong>{value}/{componentWeights[name]}</strong></div>
                        <div className="scoreTrack"><span style={{ width: `${Math.min(100, value / componentWeights[name] * 100)}%` }} /></div>
                      </div>
                    ))}
                  </div>
                  <div className="matchSkills">
                    <p><strong>Matched:</strong> {match.matched_skills.slice(0, 12).join(" · ") || "No recognized skills"}</p>
                    {match.missing_skills.length > 0 && <p><strong>Gaps:</strong> {match.missing_skills.slice(0, 8).join(" · ")}</p>}
                  </div>
                  <footer className="jobFooter">
                    <div><span>{match.job.source_name} · {match.job.source_type}</span><span>{match.job.freshness_label}</span></div>
                    <div className="jobLinks">
                      <a href={match.job.source_url} rel="noopener noreferrer" target="_blank">Evidence</a>
                      <a className="applyLink" href={match.job.application_url} rel="noopener noreferrer" target="_blank">Apply</a>
                    </div>
                  </footer>
                </article>
              ))}
            </section>
          )}
        </>
      )}
    </main>
  );
}

