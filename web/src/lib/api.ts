/**
 * API access. Every number shown in the UI comes from here; nothing is invented
 * in the browser (master prompt, non-negotiable rule 1).
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface ServiceCheck {
  ok: boolean;
  error?: string;
}

export interface Readiness {
  service: string;
  status: "ready" | "not_ready";
  version: string;
  checks: {
    database: ServiceCheck & { postgis_version?: string };
    redis: ServiceCheck;
    object_store: ServiceCheck & { bucket?: string };
    policy: ServiceCheck & { name?: string; version?: string; path?: string };
  };
}

export function readyzUrl(base: string = API_BASE): string {
  return `${base.replace(/\/$/, "")}/readyz`;
}

export async function fetchReadiness(base: string = API_BASE): Promise<Readiness> {
  const response = await fetch(readyzUrl(base), { cache: "no-store" });
  const body = (await response.json()) as Readiness;
  return body;
}
