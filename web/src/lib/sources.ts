/**
 * Source registry client. Mirrors `SourceOut` in backend/app/api/sources.py.
 * Everything the registry screen shows comes from here; nothing is invented
 * in the browser (master prompt, non-negotiable rule 1).
 */

import { API_BASE } from "./api";

export interface Source {
  source_id: string;
  name: string;
  kind: string;
  format: string;
  authority: string | null;
  licence: string;
  url: string | null;
  vintage: string | null;
  is_synthetic: boolean;
  sigma_m: number | null;
  sha256: string;
  size_bytes: number;
  object_key: string;
  crs: string | null;
  crs_source: string;
  crs_original: string | null;
  crs_declared: string | null;
  has_geometry: boolean;
  feature_count: number | null;
  coverage: number[] | null;
  attributes: string[];
  geometry_types: string[];
  layer: string | null;
  layers: string[];
  raster: Record<string, unknown> | null;
  notes: string[];
  ingested_at: string | null;
}

export interface SourceList {
  items: Source[];
  total: number;
}

export async function fetchSources(
  base: string = API_BASE,
  options: { kind?: string; limit?: number } = {},
): Promise<SourceList> {
  const params = new URLSearchParams();
  if (options.kind) params.set("kind", options.kind);
  params.set("limit", String(options.limit ?? 200));
  const response = await fetch(`${base.replace(/\/$/, "")}/sources?${params.toString()}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`GET /sources failed with ${response.status}`);
  }
  return (await response.json()) as SourceList;
}

export const KIND_LABELS: Record<string, string> = {
  drone_ori: "Drone / ORI",
  ai_extracted: "AI-extracted",
  cadastral: "Cadastral",
  revenue: "Revenue (RoR)",
  municipal: "Municipal",
  utility: "Utility",
  gnss: "GNSS survey",
  canonical: "Canonical",
};

/** Map data palette for each source kind (docs/design.md 3.3). */
export const KIND_COLORS: Record<string, string> = {
  drone_ori: "var(--layer-drone)",
  ai_extracted: "var(--layer-drone)",
  cadastral: "var(--layer-cadastral)",
  revenue: "var(--layer-revenue)",
  municipal: "var(--layer-municipal)",
  utility: "var(--layer-utility)",
  gnss: "var(--layer-municipal)",
  canonical: "var(--layer-canonical)",
};

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortSha(sha: string): string {
  return `${sha.slice(0, 8)}…${sha.slice(-6)}`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const parsed = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toISOString().slice(0, 10);
}
