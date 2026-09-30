"use client";

import { useQuery } from "@tanstack/react-query";

import {
  describeSource,
  fetchSourceHealth,
  formatDate,
  previewPngUrl,
  type Source,
} from "@/lib/sources";

/**
 * Plain-English dataset card: what the file is (from the registry fields the
 * API returned) plus what happened to it (health: loaded counts, QC flags,
 * last transform). No number here is computed in the browser.
 */
export function DatasetCard({ source }: { source: Source }) {
  const lines = describeSource(source);

  const { data: health, error: healthError, isPending } = useQuery({
    queryKey: ["source-health", source.source_id],
    queryFn: () => fetchSourceHealth(source.source_id),
    retry: 1,
  });

  const healthLines: string[] = [];
  if (health) {
    if (health.loaded.features > 0) {
      const byClass = Object.entries(health.loaded.by_class)
        .map(([label, count]) => `${label}: ${count}`)
        .join(", ");
      healthLines.push(
        `Loaded to storage: ${health.loaded.features} feature(s)${byClass ? ` (${byClass})` : ""} in EPSG:${health.storage_srid}.`,
      );
    } else if (source.raster) {
      healthLines.push(
        "Raster: no vector features — drawn on the map from its preview PNG.",
      );
    } else {
      healthLines.push(
        "No features loaded — this source is not drawn on the map (a table without geometry).",
      );
    }
    if (health.qc.flagged_features > 0) {
      const flags = Object.entries(health.qc.by_flag)
        .map(([label, count]) => `${label}: ${count}`)
        .join(", ");
      healthLines.push(
        `${health.qc.flagged_features} feature(s) carry QC flags (${flags}) and go to human review.`,
      );
    } else if (health.loaded.features > 0) {
      healthLines.push("No QC flags on the loaded features.");
    }
    if (health.transform) {
      healthLines.push(`Last storage transform: ${health.transform.pipeline}.`);
    }
  }

  return (
    <div style={{ display: "grid", gap: "8px", maxWidth: "90ch" }}>
      <p className="label" style={{ margin: 0, color: "var(--text-muted)" }}>
        Dataset card
      </p>
      <div>
        <p className="small" style={{ margin: "0 0 6px", fontWeight: 600 }}>
          {source.name}
        </p>
        <ul style={{ margin: 0, paddingLeft: "18px", display: "grid", gap: "4px" }}>
          {lines.map((line) => (
            <li key={line} className="small">
              {line}
            </li>
          ))}
          {source.notes.map((note) => (
            <li
              key={note}
              className="small"
              style={{ color: "var(--text-muted)" }}
            >
              {note}
            </li>
          ))}
        </ul>
      </div>

      {isPending && (
        <p className="small" style={{ margin: 0, color: "var(--text-muted)" }}>
          Reading <span className="data">GET /sources/…/health</span>…
        </p>
      )}
      {healthError && (
        <p className="small" style={{ margin: 0, color: "var(--text-muted)" }}>
          Health read failed; the lines above come from the registry only.
        </p>
      )}
      {healthLines.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: "18px", display: "grid", gap: "4px" }}>
          {healthLines.map((line) => (
            <li key={line} className="small">
              {line}
            </li>
          ))}
        </ul>
      )}

      {source.raster && (
        <div>
          <p className="small" style={{ margin: "0 0 4px", color: "var(--text-muted)" }}>
            Raster preview served by <span className="data">GET /sources/…/preview.png</span>:
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element -- same-origin-ish API asset, no Next image optimisation for it */}
          <img
            src={previewPngUrl(source.source_id)}
            alt={`Preview of ${source.name}`}
            style={{
              display: "block",
              width: "100%",
              maxWidth: "480px",
              border: "1px solid var(--border)",
            }}
          />
        </div>
      )}

      <p className="small" style={{ margin: 0, color: "var(--text-muted)" }}>
        Ingested {formatDate(source.ingested_at)} · SHA-256{" "}
        <span className="data">{source.sha256.slice(0, 16)}…</span>
      </p>
    </div>
  );
}
