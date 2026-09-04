"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type RefreshRun = {
  id: string;
  status: string;
  stage: string;
  started_at: string;
  finished_at: string | null;
  sources_total: number;
  sources_completed: number;
  sources_succeeded: number;
  sources_failed: number;
  sources_skipped: number;
  new_count: number;
  changed_count: number;
  verified_today_count: number;
  worldwide_count: number;
  pakistan_eligible_count: number;
  matches_scored: number;
  strict_matches: number;
  uncertain_matches: number;
  failures: Array<{ source_name?: string; message?: string }>;
  error_summary: string | null;
};

const terminalStatuses = new Set([
  "completed",
  "completed_with_errors",
  "completed_without_matching",
  "failed",
]);

const stageLabels: Record<string, string> = {
  queued: "Preparing refresh",
  ingesting: "Fetching sources",
  classifying: "Checking eligibility",
  matching: "Ranking matches",
  completed: "Refresh complete",
};

export default function RefreshControl() {
  const router = useRouter();
  const [run, setRun] = useState<RefreshRun | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  const poll = useCallback(async (runId: string) => {
    try {
      const response = await fetch(`${baseUrl}/api/v1/refresh-runs/${runId}`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Refresh status could not be loaded");
      const next = (await response.json()) as RefreshRun;
      setRun(next);
      if (terminalStatuses.has(next.status)) {
        setStarting(false);
        router.refresh();
        return;
      }
      timer.current = setTimeout(() => void poll(runId), 1200);
    } catch (caught) {
      setStarting(false);
      setError(caught instanceof Error ? caught.message : "Refresh status failed");
    }
  }, [baseUrl, router]);

  useEffect(() => {
    let cancelled = false;
    async function restoreLatest() {
      try {
        const response = await fetch(`${baseUrl}/api/v1/refresh-runs/latest`, {
          cache: "no-store",
        });
        if (!response.ok) return;
        const latest = (await response.json()) as RefreshRun;
        if (cancelled) return;
        setRun(latest);
        if (!terminalStatuses.has(latest.status)) {
          setStarting(true);
          void poll(latest.id);
        }
      } catch {
        // No prior refresh is a valid first-run state.
      }
    }
    void restoreLatest();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [baseUrl, poll]);

  async function startRefresh() {
    setStarting(true);
    setError(null);
    if (timer.current) clearTimeout(timer.current);
    try {
      const response = await fetch(`${baseUrl}/api/v1/refresh-runs`, { method: "POST" });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(detail?.detail ?? "Refresh could not be started");
      }
      const started = (await response.json()) as RefreshRun;
      setRun(started);
      void poll(started.id);
    } catch (caught) {
      setStarting(false);
      setError(caught instanceof Error ? caught.message : "Refresh failed");
    }
  }

  const active = starting || (run !== null && !terminalStatuses.has(run.status));
  const progress = run?.sources_total
    ? Math.round((run.sources_completed / run.sources_total) * 100)
    : 0;

  return (
    <section className="refreshPanel" aria-live="polite">
      <div className="refreshTop">
        <div>
          <p className="eyebrow">DAILY DISCOVERY</p>
          <h2>Fetch and rank the latest jobs</h2>
          <p>Checks every enabled source, verifies location eligibility, then matches against your current resume.</p>
        </div>
        <button type="button" onClick={startRefresh} disabled={active}>
          {active ? "Refresh running…" : run ? "Fetch again" : "Fetch today's jobs"}
        </button>
      </div>

      {run && (
        <div className="refreshStatus">
          <div className="refreshStatusLine">
            <strong>{stageLabels[run.stage] ?? run.stage}</strong>
            <span>{run.sources_completed} of {run.sources_total} sources checked</span>
          </div>
          <div className="refreshTrack"><span style={{ width: `${progress}%` }} /></div>
          {terminalStatuses.has(run.status) && (
            <div className="refreshMetrics">
              <span><strong>{run.new_count}</strong> new</span>
              <span><strong>{run.changed_count}</strong> changed</span>
              <span><strong>{run.verified_today_count}</strong> verified today</span>
              <span><strong>{run.worldwide_count}</strong> worldwide</span>
              <span><strong>{run.pakistan_eligible_count}</strong> Pakistan eligible</span>
              <span><strong>{run.strict_matches}</strong> ranked matches</span>
            </div>
          )}
          {run.sources_failed > 0 && (
            <p className="refreshWarning">
              {run.sources_failed} source{run.sources_failed === 1 ? "" : "s"} failed; previous jobs were preserved.
            </p>
          )}
          {run.status === "completed_without_matching" && (
            <p className="refreshWarning">Jobs were refreshed, but no current resume profile exists.</p>
          )}
          {run.error_summary && <p className="refreshWarning">{run.error_summary}</p>}
        </div>
      )}
      {error && <p className="refreshWarning">{error}</p>}
    </section>
  );
}
