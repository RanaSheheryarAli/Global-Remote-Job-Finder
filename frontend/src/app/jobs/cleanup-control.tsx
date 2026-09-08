"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type CleanupResult = {
  deleted_jobs: number;
  deleted_rejections: number;
};

export default function CleanupControl() {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function cleanup() {
    const approved = window.confirm(
      "Delete every job older than 24 hours? This permanently removes related matches and snapshots.",
    );
    if (!approved) return;

    setRunning(true);
    setMessage(null);
    setError(null);
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/jobs/cleanup?confirm=delete-old-jobs&older_than_hours=24`,
        { method: "DELETE" },
      );
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Cleanup failed (${response.status})`);
      }
      const result = (await response.json()) as CleanupResult;
      setMessage(`${result.deleted_jobs} old jobs removed.`);
      router.replace("/jobs");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Cleanup failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="cleanupControl">
      <button type="button" onClick={cleanup} disabled={running}>
        {running ? "Removing old jobs…" : "Remove jobs older than 24h"}
      </button>
      {message && <span className="cleanupSuccess">{message}</span>}
      {error && <span className="cleanupError">{error}</span>}
    </div>
  );
}
