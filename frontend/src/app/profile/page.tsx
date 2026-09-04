type Profile = {
  id: string;
  version: number;
  is_current: boolean;
  resume_filename: string;
  resume_sha256: string;
  full_name: string;
  headline: string;
  location: string | null;
  timezone: string;
  years_experience: number;
  role_families: string[];
  seniority_levels: string[];
  skills: Record<string, string[]>;
  cloud_platforms: string[];
  domains: string[];
  preferences: Record<string, unknown>;
  extraction_evidence: Record<string, unknown>;
  created_at: string;
};

type Summary = {
  profile_version: number;
  matcher_version: number;
  total_scored: number;
  strong: number;
  good: number;
  possible: number;
  strict_visible: number;
  uncertain_visible: number;
  excluded: number;
};

async function getProfile(): Promise<{ profile: Profile | null; summary: Summary | null }> {
  const baseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";
  try {
    const [profileResponse, summaryResponse] = await Promise.all([
      fetch(`${baseUrl}/api/v1/profile`, { cache: "no-store" }),
      fetch(`${baseUrl}/api/v1/matches/summary`, { cache: "no-store" }),
    ]);
    return {
      profile: profileResponse.ok ? ((await profileResponse.json()) as Profile) : null,
      summary: summaryResponse.ok ? ((await summaryResponse.json()) as Summary) : null,
    };
  } catch {
    return { profile: null, summary: null };
  }
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default async function ProfilePage() {
  const { profile, summary } = await getProfile();
  return (
    <main>
      <header className="adminHeader jobsHeader">
        <div>
          <p className="eyebrow">RESUME PROFILE</p>
          <h1>Candidate profile</h1>
          <p className="lead jobsLead">
            Reviewable resume facts used by the deterministic job matcher.
          </p>
        </div>
      </header>

      {!profile ? (
        <section className="emptyState">
          <h2>No profile yet</h2>
          <p>Upload the existing PDF through the private resume API, then rebuild matches.</p>
        </section>
      ) : (
        <>
          <section className="profileHero">
            <div>
              <p className="eyebrow">PROFILE VERSION {profile.version}</p>
              <h2>{profile.full_name}</h2>
              <p>{profile.headline}</p>
              <div className="badgeRow">
                <span>{profile.location ?? "Location unavailable"}</span>
                <span>{profile.timezone}</span>
                <span>{profile.years_experience}+ years</span>
              </div>
            </div>
            <div className="privacyStamp">
              <strong>Original PDF unchanged</strong>
              <span>{profile.resume_filename}</span>
              <code>SHA-256 {profile.resume_sha256.slice(0, 16)}…</code>
            </div>
          </section>

          {summary && (
            <section className="metricGrid trustMetrics" aria-label="Match summary">
              <article className="metric"><strong>{summary.total_scored}</strong><span>Jobs scored</span></article>
              <article className="metric"><strong>{summary.strong}</strong><span>Strong matches</span></article>
              <article className="metric"><strong>{summary.good}</strong><span>Good matches</span></article>
              <article className="metric"><strong>{summary.strict_visible}</strong><span>Strictly eligible</span></article>
            </section>
          )}

          <section className="profileGrid">
            <article className="profilePanel">
              <p className="eyebrow">TARGETING</p>
              <h2>Role families</h2>
              <div className="skillCloud">
                {profile.role_families.map((role) => <span key={role}>{humanize(role)}</span>)}
              </div>
              <h3>Seniority evidence</h3>
              <div className="skillCloud">
                {profile.seniority_levels.map((level) => <span key={level}>{humanize(level)}</span>)}
              </div>
            </article>
            <article className="profilePanel">
              <p className="eyebrow">CONTEXT</p>
              <h2>Cloud & domains</h2>
              <h3>Cloud platforms</h3>
              <div className="skillCloud">
                {profile.cloud_platforms.map((item) => <span key={item}>{item}</span>)}
              </div>
              <h3>Domains</h3>
              <div className="skillCloud">
                {profile.domains.map((item) => <span key={item}>{humanize(item)}</span>)}
              </div>
            </article>
          </section>

          <section className="skillsSection">
            <p className="eyebrow">NORMALIZED ONTOLOGY</p>
            <h2>Skills extracted from the resume</h2>
            <div className="skillsGrid">
              {Object.entries(profile.skills).map(([category, skills]) => (
                <article className="skillGroup" key={category}>
                  <h3>{humanize(category)}</h3>
                  <p>{skills.join(" · ")}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
