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

/** Mirrors `source_health` in backend/app/crs/service.py (`GET /sources/{id}/health`). */
export interface SourceHealth {
  source_id: string;
  name: string;
  kind: string;
  storage_srid: number;
  declared_crs: string | null;
  crs_source: string;
  coverage: number[] | null;
  has_geometry: boolean;
  schema: { attributes: string[]; geometry_types: string[]; layer: string | null };
  loaded: { features: number; by_class: Record<string, number> };
  qc: { flagged_features: number; by_flag: Record<string, number> };
  transform: {
    pipeline: string;
    n_control: number | null;
    rmse_m: number | null;
    max_resid_m: number | null;
    created_at: string | null;
  } | null;
  georef: Record<string, unknown> | null;
}

/** The GeoJSON served by `GET /sources/{id}/features.geojson`. */
export interface SourceFeatures {
  type: "FeatureCollection";
  features: unknown[];
  total: number;
  source?: { source_id: string; name: string; kind: string };
  truncated?: boolean;
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

export async function fetchSourceHealth(id: string, base: string = API_BASE): Promise<SourceHealth> {
  const response = await fetch(`${base.replace(/\/$/, "")}/sources/${id}/health`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`GET /sources/{id}/health failed with ${response.status}`);
  }
  return (await response.json()) as SourceHealth;
}

export async function fetchSourceFeatures(
  id: string,
  base: string = API_BASE,
): Promise<SourceFeatures> {
  const response = await fetch(`${base.replace(/\/$/, "")}/sources/${id}/features.geojson`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`GET /sources/{id}/features.geojson failed with ${response.status}`);
  }
  return (await response.json()) as SourceFeatures;
}

/** `GET /sources/{id}/preview` — where a raster sits on the map (WGS 84). */
export interface PreviewInfo {
  source_id: string;
  name: string;
  bounds: [number, number, number, number];
  width: number;
  height: number;
  png: string;
}

export async function fetchSourcePreview(
  id: string,
  base: string = API_BASE,
): Promise<PreviewInfo> {
  const response = await fetch(`${base.replace(/\/$/, "")}/sources/${id}/preview`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`GET /sources/{id}/preview failed with ${response.status}`);
  }
  return (await response.json()) as PreviewInfo;
}

export function previewPngUrl(id: string, base: string = API_BASE): string {
  return `${base.replace(/\/$/, "")}/sources/${id}/preview.png`;
}

export interface UploadSourceInput {
  file: File;
  name: string;
  kind: string;
  licence: string;
  authority?: string;
  vintage?: string;
  sigmaM?: number;
  isSynthetic?: boolean;
  declaredCrs?: string;
}

/** `POST /sources` — one multipart upload; returns the registered row. */
export async function uploadSource(
  input: UploadSourceInput,
  base: string = API_BASE,
): Promise<Source> {
  const form = new FormData();
  form.set("file", input.file);
  form.set("name", input.name);
  form.set("kind", input.kind);
  form.set("licence", input.licence);
  if (input.authority) form.set("authority", input.authority);
  if (input.vintage) form.set("vintage", input.vintage);
  if (input.sigmaM !== undefined && !Number.isNaN(input.sigmaM)) {
    form.set("sigma_m", String(input.sigmaM));
  }
  form.set("is_synthetic", input.isSynthetic ? "true" : "false");
  if (input.declaredCrs) form.set("declared_crs", input.declaredCrs);

  const response = await fetch(`${base.replace(/\/$/, "")}/sources`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    let message = `upload failed with ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      const detail = body.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        const record = detail as Record<string, unknown>;
        if (typeof record.message === "string") message = record.message;
        else if (typeof record.code === "string") message = record.code;
      }
    } catch {
      // keep the status-line message when the body is not JSON
    }
    throw new Error(message);
  }
  return (await response.json()) as Source;
}

export const KIND_LABELS: Record<string, string> = {
  drone_ori: "Drone / ORI",
  satellite: "Satellite imagery",
  dsm: "DSM (elevation)",
  dtm: "DTM (elevation)",
  cadastral: "Cadastral",
  revenue: "Revenue (RoR)",
  municipal: "Municipal",
  utility: "Utility",
  gnss: "GNSS survey",
  footprint_ai: "AI footprint",
  footprint_ref: "Reference footprint",
  canonical: "Canonical",
};

/** Map data palette for each source kind (docs/design.md 3.3). */
export const KIND_COLORS: Record<string, string> = {
  drone_ori: "var(--layer-drone)",
  satellite: "var(--layer-satellite)",
  dsm: "var(--layer-drone)",
  dtm: "var(--layer-utility)",
  cadastral: "var(--layer-cadastral)",
  revenue: "var(--layer-revenue)",
  municipal: "var(--layer-municipal)",
  utility: "var(--layer-utility)",
  gnss: "var(--layer-municipal)",
  footprint_ai: "var(--layer-drone)",
  footprint_ref: "var(--layer-canonical)",
  canonical: "var(--layer-canonical)",
};

/**
 * Same palette as plain hex values for MapLibre, which cannot resolve CSS
 * variables inside paint properties.
 */
export const KIND_HEX: Record<string, string> = {
  drone_ori: "#f26a1b",
  satellite: "#933b08",
  dsm: "#f26a1b",
  dtm: "#e7a400",
  cadastral: "#1a1712",
  revenue: "#d9327a",
  municipal: "#8fbf00",
  utility: "#e7a400",
  gnss: "#8fbf00",
  footprint_ai: "#f26a1b",
  footprint_ref: "#1f7a3e",
  canonical: "#1f7a3e",
};

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function kindHex(kind: string): string {
  return KIND_HEX[kind] ?? "#8fbf00";
}

/**
 * Map colour roles (docs/design.md 3.3). The map colours layers by ROLE —
 * what the data is for — instead of by the twelve registry kinds, so the
 * legend stays four colours: lime = municipal context, dark green = reference,
 * marigold = synthetic demo, chilli red = boundary/attention (static layers).
 */
export type MapRole = "basemap" | "context" | "reference" | "synthetic";

export const ROLE_HEX: Record<MapRole, string> = {
  basemap: "#6b6252",
  context: "#8fbf00",
  reference: "#1f7a3e",
  synthetic: "#f26a1b",
};

export function mapRole(isSynthetic: boolean, kind: string): { role: MapRole; hex: string } {
  if (isSynthetic) return { role: "synthetic", hex: ROLE_HEX.synthetic };
  if (kind === "municipal" || kind === "gnss") return { role: "context", hex: ROLE_HEX.context };
  return { role: "reference", hex: ROLE_HEX.reference };
}

const FORMAT_LABELS: Record<string, string> = {
  geotiff: "GeoTIFF",
  geojson: "GeoJSON",
  gpkg: "GeoPackage",
  shapefile: "shapefile",
  csv_gnss: "GNSS CSV",
  csv_ror: "revenue CSV",
};

export function formatLabel(format: string): string {
  return FORMAT_LABELS[format] ?? format;
}

const CRS_SOURCE_LABELS: Record<string, string> = {
  file: "read from the file itself",
  declared: "declared by the uploader",
  implicit_wgs84: "assumed to be WGS 84",
  none: "not established",
};

export function crsSourceLabel(crsSource: string): string {
  return CRS_SOURCE_LABELS[crsSource] ?? crsSource;
}

/**
 * Plain-English description of one registered source, built only from fields
 * the API returned. Used by the dataset card on the Sources screen.
 */
export function describeSource(source: Source): string[] {
  const lines: string[] = [];
  const fmt = formatLabel(source.format);
  const kind = kindLabel(source.kind).toLowerCase();

  if (source.raster) {
    const raster = source.raster as {
      width?: number;
      height?: number;
      bands?: number;
      resolution?: number[];
    };
    lines.push(`A ${fmt} raster of ${kind} data, ${formatBytes(source.size_bytes)}.`);
    if (typeof raster.width === "number" && typeof raster.height === "number") {
      lines.push(
        `${raster.width} × ${raster.height} pixels, ${raster.bands ?? 1} band(s).`,
      );
    }
    if (Array.isArray(raster.resolution) && raster.resolution.length === 2) {
      lines.push(`Pixel size ${raster.resolution[0]} × ${raster.resolution[1]} (file units).`);
    }
  } else if (source.has_geometry) {
    const count = source.feature_count ?? "an unknown number of";
    lines.push(
      `A ${fmt} file of ${kind} data, ${formatBytes(source.size_bytes)}, with ${count} feature(s).`,
    );
    if (source.geometry_types.length > 0) {
      lines.push(`Geometries: ${source.geometry_types.join(", ")}.`);
    }
    if (source.attributes.length > 0) {
      const shown = source.attributes.slice(0, 8).join(", ");
      const rest = source.attributes.length > 8 ? `, … (${source.attributes.length} total)` : "";
      lines.push(`Attributes carried: ${shown}${rest}.`);
    }
  } else {
    lines.push(
      `A ${fmt} table of ${kind} data, ${formatBytes(source.size_bytes)}, with ${source.feature_count ?? 0} row(s) and no geometry.`,
    );
    if (source.attributes.length > 0) {
      lines.push(`Columns: ${source.attributes.join(", ")}.`);
    }
  }

  if (source.crs) {
    lines.push(`Coordinates are read as ${source.crs} (${crsSourceLabel(source.crs_source)}).`);
  } else if (!source.has_geometry) {
    lines.push("No coordinates: this is a record table, not a map layer.");
  }

  if (source.coverage && source.coverage.length === 4) {
    const [minx, miny, maxx, maxy] = source.coverage as [number, number, number, number];
    lines.push(
      `Extent from (${minx.toFixed(5)}, ${miny.toFixed(5)}) to (${maxx.toFixed(5)}, ${maxy.toFixed(5)}) in the file's own coordinates.`,
    );
  }
  if (source.sigma_m !== null && source.sigma_m !== undefined) {
    lines.push(`Assumed positional accuracy ±${source.sigma_m} m.`);
  }
  if (source.authority) {
    lines.push(`From ${source.authority}.`);
  }
  if (source.vintage) {
    lines.push(`Vintage ${source.vintage}.`);
  }
  if (source.layer) {
    lines.push(`Layer read: ${source.layer}.`);
  }
  if (source.is_synthetic) {
    lines.push("SYNTHETIC — generated for testing, not evidence about real parcels.");
  }
  return lines;
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
