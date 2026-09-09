"use client";

import { useRouter } from "next/navigation";
import { ChangeEvent, useState } from "react";

const MAX_BYTES = 2_000_000;

export default function ResumeUpload() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setMessage(null);
    setError(null);
    if (selected && !selected.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setError("Please select a PDF resume.");
      return;
    }
    if (selected && selected.size > MAX_BYTES) {
      setFile(null);
      setError("Resume must be smaller than 2 MB.");
      return;
    }
    setFile(selected);
  }

  async function upload() {
    if (!file) return;
    setUploading(true);
    setMessage(null);
    setError(null);
    try {
      const response = await fetch(
        `${baseUrl}/api/v1/resume?filename=${encodeURIComponent(file.name)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/pdf" },
          body: file,
        },
      );
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail ?? `Resume upload failed (${response.status})`);
      }

      const rebuild = await fetch(`${baseUrl}/api/v1/matches/rebuild`, { method: "POST" });
      if (!rebuild.ok) {
        throw new Error("Resume was saved, but job matches could not be rebuilt.");
      }
      setMessage("New resume uploaded and all jobs re-matched.");
      setFile(null);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Resume upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="resumeUpload" aria-live="polite">
      <div>
        <p className="eyebrow">UPDATE MATCHING PROFILE</p>
        <h2>Upload a new resume</h2>
        <p>
          Select a PDF. A new private profile version is created and every saved job is
          scored again against the new resume.
        </p>
      </div>
      <div className="resumeUploadActions">
        <label className="filePicker">
          <span>{file ? file.name : "Choose PDF"}</span>
          <input accept="application/pdf,.pdf" onChange={selectFile} type="file" />
        </label>
        <button disabled={!file || uploading} onClick={upload} type="button">
          {uploading ? "Uploading and matching…" : "Upload & re-match"}
        </button>
        {message && <small className="uploadSuccess">{message}</small>}
        {error && <small className="uploadError">{error}</small>}
      </div>
    </section>
  );
}
