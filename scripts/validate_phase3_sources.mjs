import { readFile } from "node:fs/promises";
import process from "node:process";

const registryUrl = new URL(
  "../backend/app/registry/phase3_sources.json",
  import.meta.url,
);
const registry = JSON.parse(await readFile(registryUrl, "utf8"));

function providerUrl(source) {
  if (source.source_type === "greenhouse") {
    return `https://boards-api.greenhouse.io/v1/boards/${source.board_token}/jobs`;
  }
  if (source.source_type === "lever") {
    const host = source.provider_region === "eu" ? "api.eu.lever.co" : "api.lever.co";
    return `https://${host}/v0/postings/${source.board_token}?mode=json`;
  }
  if (source.source_type === "ashby") {
    return `https://api.ashbyhq.com/posting-api/job-board/${source.board_token}?includeCompensation=true`;
  }
  return "https://remoteok.com/api";
}

function inspectPayload(source, payload) {
  if (source.source_type === "greenhouse") {
    const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
    return { jobs: jobs.length, sampleUrl: jobs[0]?.absolute_url };
  }
  if (source.source_type === "lever") {
    const jobs = Array.isArray(payload) ? payload : [];
    return { jobs: jobs.length, sampleUrl: jobs[0]?.hostedUrl };
  }
  if (source.source_type === "ashby") {
    const jobs = Array.isArray(payload.jobs)
      ? payload.jobs.filter((job) => job.isListed !== false)
      : [];
    return { jobs: jobs.length, sampleUrl: jobs[0]?.jobUrl };
  }

  const metadata = Array.isArray(payload) ? payload[0] : null;
  const legal = String(metadata?.legal ?? "").toLowerCase();
  if (!legal.includes("link back") || !legal.includes("remote ok")) {
    throw new Error("Remote OK attribution terms are missing or changed");
  }
  const jobs = payload.slice(1).filter((job) => job && job.id);
  return { jobs: jobs.length, sampleUrl: jobs[0]?.url };
}

async function validate(source) {
  const endpoint = providerUrl(source);
  try {
    const response = await fetch(endpoint, {
      headers: { "User-Agent": "GlobalRemoteJobTool-Phase3-Validator/1.0" },
      signal: AbortSignal.timeout(20_000),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    const result = inspectPayload(source, payload);
    if (result.jobs < 1) {
      throw new Error("No published jobs returned")
    }
    const sample = new URL(result.sampleUrl);
    if (sample.protocol !== "https:") {
      throw new Error("Sample source URL is not HTTPS");
    }
    return {
      name: source.name,
      provider: source.source_type,
      status: "healthy",
      jobs: result.jobs,
      sample_url: result.sampleUrl,
    };
  } catch (error) {
    return {
      name: source.name,
      provider: source.source_type,
      status: "failed",
      jobs: 0,
      error: error.message,
    };
  }
}

async function mapWithConcurrency(items, limit, worker) {
  const results = new Array(items.length);
  let next = 0;
  async function runner() {
    while (next < items.length) {
      const index = next++;
      results[index] = await worker(items[index]);
    }
  }
  await Promise.all(Array.from({ length: limit }, runner));
  return results;
}

const results = await mapWithConcurrency(registry.sources, 4, validate);
console.table(
  results.map(({ name, provider, status, jobs }) => ({ name, provider, status, jobs })),
);
const failed = results.filter((result) => result.status !== "healthy");
console.log(
  JSON.stringify(
    {
      checked_at: new Date().toISOString(),
      definitions: results.length,
      healthy: results.length - failed.length,
      failed: failed.length,
      failures: failed,
    },
    null,
    2,
  ),
);
if (failed.length) {
  process.exitCode = 1;
}

