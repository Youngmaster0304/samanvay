"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { KindTag, SyntheticBadge } from "@/components/badges";
import {
  fetchSources,
  formatBytes,
  formatDate,
  kindLabel,
  shortSha,
  type Source,
} from "@/lib/sources";

const TH: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px 8px 0",
  borderBottom: "1px solid var(--border-ctl)",
  whiteSpace: "nowrap",
  position: "sticky",
  top: 0,
  background: "var(--surface)",
  zIndex: 1,
};

const TD: React.CSSProperties = {
  padding: "0 12px 0 0",
  height: "36px",
  whiteSpace: "nowrap",
  fontVariantNumeric: "tabular-nums",
};

export default function SourcesPage() {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");

  const { data, error, isPending, refetch, isFetching } = useQuery({
    queryKey: ["sources"],
    queryFn: () => fetchSources(),
    retry: 1,
  });

  const kinds = useMemo(() => {
    const seen = new Set<string>();
    for (const item of data?.items ?? []) seen.add(item.kind);
    return [...seen].sort();
  }, [data]);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.items ?? []).filter((item) => {
      if (kind && item.kind !== kind) return false;
      if (!needle) return true;
      return [item.name, item.authority ?? "", item.licence, item.format]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [data, kind, query]);

  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "baseline", justifyContent: "space-between" }}>
        <div>
          <p className="label" style={{ color: "var(--text-muted)", margin: "0 0 4px" }}>
            Registry
          </p>
          <h1 className="h1" style={{ margin: "0 0 4px" }}>
            Sources
          </h1>
        </div>
        <button type="button" className="btn btn--secondary" onClick={() => void refetch()} disabled={isFetching}>
          {isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <p className="small" style={{ color: "var(--text-muted)", margin: "0 0 16px", maxWidth: "72ch" }}>
        Every row is one registered upload: its licence, vintage, checksum and CRS are recorded as
        supplied and can be read back from <span className="data">GET /sources</span>. The health
        columns (residual RMSE, coverage) are not charted yet; loaded-feature counts and QC flags
        per source read from <span className="data">{"GET /sources/{id}/health"}</span>.
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center", marginBottom: "14px" }}>
        <label className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          Search
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="name, authority, licence…"
            style={{
              minHeight: "36px",
              padding: "0 10px",
              border: "1px solid var(--border-ctl)",
              borderRadius: "var(--radius-control)",
              background: "var(--surface)",
              color: "var(--text)",
              font: "inherit",
              minWidth: "220px",
            }}
          />
        </label>

        <label className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          Kind
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value)}
            style={{
              minHeight: "36px",
              padding: "0 8px",
              border: "1px solid var(--border-ctl)",
              borderRadius: "var(--radius-control)",
              background: "var(--surface)",
              color: "var(--text)",
              font: "inherit",
            }}
          >
            <option value="">All kinds</option>
            {kinds.map((value) => (
              <option key={value} value={value}>
                {kindLabel(value)}
              </option>
            ))}
          </select>
        </label>

        {data && (
          <span className="data" style={{ color: "var(--text-muted)" }}>
            {rows.length} of {data.total}
          </span>
        )}
      </div>

      {isPending && (
        <p className="small" style={{ color: "var(--text-muted)" }}>
          Contacting <span className="data">GET /sources</span>…
        </p>
      )}

      {error && (
        <EmptyState
          title="Cannot reach the source registry"
          body={`GET /sources failed: ${error instanceof Error ? error.message : "request failed"}. The registry lives in the API, so the stack has to be running.`}
          note="docker compose up -d   # then Refresh"
        />
      )}

      {data && data.total === 0 && (
        <EmptyState
          title="No sources registered"
          body="Register the first dataset — a GeoTIFF, GeoJSON, GeoPackage, shapefile or CSV — to give the workbench something real to align."
          actionLabel="Read the data checklist"
          actionHref="/about"
        />
      )}

      {data && data.total > 0 && rows.length === 0 && (
        <EmptyState
          title="No source matches this filter"
          body="The registry still holds rows; the current search or kind filter hides all of them."
        />
      )}

      {data && rows.length > 0 && (
        <div className="panel" style={{ overflowX: "auto", padding: "12px 16px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <caption className="label" style={{ textAlign: "left", padding: "0 0 10px", color: "var(--text-muted)" }}>
              {data.total} registered source{data.total === 1 ? "" : "s"}, newest first
            </caption>
            <thead>
              <tr>
                <th scope="col" style={TH}>Name</th>
                <th scope="col" style={TH}>Kind</th>
                <th scope="col" style={TH}>Format</th>
                <th scope="col" style={TH}>Authority</th>
                <th scope="col" style={TH}>Vintage</th>
                <th scope="col" style={TH}>CRS</th>
                <th scope="col" style={{ ...TH, textAlign: "right" }}>Features</th>
                <th scope="col" style={{ ...TH, textAlign: "right" }}>Sigma (m)</th>
                <th scope="col" style={TH}>Licence</th>
                <th scope="col" style={TH}>Checksum</th>
                <th scope="col" style={{ ...TH, textAlign: "right" }}>Size</th>
                <th scope="col" style={TH}>Ingested</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((source, index) => (
                <SourceRow key={source.source_id} source={source} striped={index % 2 === 1} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function SourceRow({ source, striped }: { source: Source; striped: boolean }) {
  return (
    <tr
      style={{
        background: striped ? "var(--paper-100)" : "transparent",
        borderTop: "1px solid var(--border)",
      }}
    >
      <th scope="row" style={{ ...TD, textAlign: "left", fontWeight: 500 }}>
        <span style={{ display: "inline-flex", gap: "8px", alignItems: "center" }}>
          {source.name}
          {source.is_synthetic && <SyntheticBadge />}
        </span>
        {source.notes.length > 0 && (
          <span
            className="small"
            style={{ display: "block", color: "var(--text-muted)", fontWeight: 400, maxWidth: "38ch", overflow: "hidden", textOverflow: "ellipsis" }}
            title={source.notes.join(" · ")}
          >
            {source.notes.join(" · ")}
          </span>
        )}
      </th>
      <td style={TD}>
        <KindTag kind={source.kind} />
      </td>
      <td className="data" style={TD}>{source.format}</td>
      <td style={TD}>{source.authority ?? "—"}</td>
      <td className="data" style={TD}>{source.vintage ?? "—"}</td>
      <td className="data" style={TD} title={`declared ${source.crs_declared ?? "—"} · original ${source.crs_original ?? "—"}`}>
        {source.crs ?? "—"} <span style={{ color: "var(--text-muted)" }}>({source.crs_source})</span>
      </td>
      <td className="data" style={{ ...TD, textAlign: "right" }}>
        {source.feature_count ?? (source.raster ? "raster" : "—")}
      </td>
      <td className="data" style={{ ...TD, textAlign: "right" }}>{source.sigma_m ?? "—"}</td>
      <td style={TD}>
        {source.url ? (
          <a href={source.url} target="_blank" rel="noreferrer">
            {source.licence}
          </a>
        ) : (
          source.licence
        )}
      </td>
      <td className="data" style={TD} title={source.sha256}>{shortSha(source.sha256)}</td>
      <td className="data" style={{ ...TD, textAlign: "right" }}>{formatBytes(source.size_bytes)}</td>
      <td className="data" style={TD}>{formatDate(source.ingested_at)}</td>
    </tr>
  );
}
