"use client";

import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Eye, EyeOff, Search } from "lucide-react";

import {
  MapCanvas,
  SECTOR22_BBOX,
  type DynamicLayer,
  type ImageLayer,
  type LayerVisibility,
} from "@/components/map-canvas";
import {
  fetchSourceFeatures,
  fetchSourcePreview,
  fetchSources,
  kindLabel,
  mapRole,
  previewPngUrl,
  type MapRole,
} from "@/lib/sources";

type LayerGroup = "Basemap" | "Overlays" | "Registry";

interface LayerRow {
  key: string;
  label: string;
  meta: string;
  group: LayerGroup;
  role: MapRole;
  raster?: boolean;
  defaultOn: boolean;
}

interface RegistryLayer extends DynamicLayer {
  meta: string;
  role: MapRole;
  synthetic: boolean;
}

/** The two municipal OSM sources are already drawn from static files. */
const STATIC_OVERLAY_NAMES = new Set([
  "OSM Sector 22 roads",
  "OSM Sector 22 municipal boundary",
]);

const LAYERS: LayerRow[] = [
  {
    key: "satellite",
    label: "Satellite imagery",
    meta: "Raster · Tiles © Esri, Maxar, Earthstar Geographics",
    group: "Basemap",
    role: "basemap",
    raster: true,
    defaultOn: true,
  },
  {
    key: "osm",
    label: "OSM basemap",
    meta: "Raster · © OpenStreetMap contributors, ODbL 1.0",
    group: "Basemap",
    role: "basemap",
    raster: true,
    defaultOn: false,
  },
  {
    key: "boundary",
    label: "Sector 22 boundary",
    meta: "Municipal · OSM relation 7894503 · 2026-09-30",
    group: "Overlays",
    role: "context",
    defaultOn: true,
  },
  {
    key: "roads",
    label: "Sector 22 roads",
    meta: "Municipal · 494 ways · ODbL 1.0",
    group: "Overlays",
    role: "context",
    defaultOn: true,
  },
];

const GROUPS: LayerGroup[] = ["Basemap", "Overlays", "Registry"];

/** Legend sections, in display order; each maps one map colour to its meaning. */
const LEGEND_GROUPS: { role: MapRole; title: string; note: string }[] = [
  {
    role: "context",
    title: "Context — real municipal data",
    note: "Lime, boundary red · roads, land use, parks, wards (© OpenStreetMap, ODbL)",
  },
  {
    role: "reference",
    title: "Reference — real data",
    note: "Dark green · buildings and other reference layers to align against",
  },
  {
    role: "synthetic",
    title: "Synthetic — demo data",
    note: "Marigold · generated for the demo, never real records",
  },
  {
    role: "basemap",
    title: "Basemap",
    note: "Satellite imagery and the alternative OSM base layer",
  },
];

const FLOW = [
  { step: "01", label: "Upload data", hint: "Register & load", href: "/sources" },
  { step: "02", label: "Auto-harmonize", hint: "CRS fit · QC flags", href: "/queue/conflicts" },
  { step: "03", label: "Result", hint: "Layers & queue", href: "/map" },
] as const;

function bboxOfFeatures(
  features: unknown[],
): [number, number, number, number] | null {
  let minx = Infinity;
  let miny = Infinity;
  let maxx = -Infinity;
  let maxy = -Infinity;
  const walk = (node: unknown): void => {
    if (!Array.isArray(node)) return;
    if (typeof node[0] === "number" && typeof node[1] === "number") {
      const x = node[0];
      const y = node[1];
      if (x < minx) minx = x;
      if (y < miny) miny = y;
      if (x > maxx) maxx = x;
      if (y > maxy) maxy = y;
      return;
    }
    for (const child of node) walk(child);
  };
  for (const feature of features) {
    const geometry = (feature as { geometry?: { coordinates?: unknown } }).geometry;
    if (geometry?.coordinates) walk(geometry.coordinates);
  }
  if (!Number.isFinite(minx) || !Number.isFinite(miny)) return null;
  return [minx, miny, maxx, maxy];
}

function LayerPreview({
  layer,
  color,
  raster,
}: {
  layer: string;
  color?: string;
  raster?: boolean;
}) {
  if (raster) {
    return (
      <span
        aria-hidden="true"
        style={{
          width: "20px",
          height: "14px",
          background: "linear-gradient(135deg, #1a1712 0%, #1f7a3e 55%, #8fbf00 100%)",
          border: "1px solid var(--ink-900)",
          borderRadius: "2px",
          display: "block",
        }}
      />
    );
  }
  if (color) {
    return (
      <span
        aria-hidden="true"
        style={{ width: "20px", height: "3px", background: color, display: "block" }}
      />
    );
  }
  if (layer === "roads") {
    return (
      <span
        aria-hidden="true"
        style={{ width: "20px", height: "3px", background: "var(--layer-municipal)", display: "block" }}
      />
    );
  }
  if (layer === "boundary") {
    return (
      <span
        aria-hidden="true"
        style={{ width: "20px", height: "3px", background: "var(--layer-conflict)", display: "block" }}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      style={{
        width: "20px",
        height: "14px",
        background: "var(--paper-200)",
        border: "1px solid var(--ink-900)",
        borderRadius: "2px",
        display: "block",
      }}
    />
  );
}

export default function MapPage() {
  const [visible, setVisible] = useState<LayerVisibility>({
    satellite: true,
    osm: false,
    boundary: true,
    roads: true,
  });
  const [query, setQuery] = useState("");
  const [fitKey, setFitKey] = useState(0);
  const [tab, setTab] = useState<"layers" | "map">("map");

  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: () => fetchSources(),
    retry: 1,
  });

  const candidateIds = useMemo(
    () =>
      (sources?.items ?? [])
        .filter(
          (item) =>
            item.has_geometry && !item.raster && !STATIC_OVERLAY_NAMES.has(item.name),
        )
        .map((item) => item.source_id),
    [sources],
  );

  const { data: registryLayers } = useQuery<RegistryLayer[]>({
    queryKey: ["map-registry-layers", candidateIds.join(",")],
    enabled: candidateIds.length > 0,
    queryFn: async () => {
      const fetched = await Promise.all(
        candidateIds.map(async (id) => {
          try {
            const features = await fetchSourceFeatures(id);
            if (features.features.length === 0) return null;
            const item = sources?.items.find((entry) => entry.source_id === id);
            const kind = item?.kind ?? features.source?.kind ?? "";
            const synthetic = item?.is_synthetic ?? false;
            const { role, hex } = mapRole(synthetic, kind);
            const total = features.total;
            const drawn = features.features.length;
            return {
              id,
              label: features.source?.name ?? "Registry layer",
              color: hex,
              role,
              synthetic,
              meta: `${kindLabel(kind)} · ${total} feature(s)${
                features.truncated ? ` (first ${drawn} drawn)` : ""
              }`,
              data: features as unknown as GeoJSON.FeatureCollection,
              bbox: bboxOfFeatures(features.features),
            } satisfies RegistryLayer;
          } catch {
            return null;
          }
        }),
      );
      return fetched.filter((layer): layer is RegistryLayer => layer !== null);
    },
  });

  const rasterIds = useMemo(
    () =>
      (sources?.items ?? [])
        .filter((item) => item.raster !== null && item.coverage !== null)
        .map((item) => item.source_id),
    [sources],
  );

  type PreviewLayer = ImageLayer & {
    meta: string;
    color: string;
    role: MapRole;
    synthetic: boolean;
  };

  const { data: imageLayers } = useQuery<PreviewLayer[]>({
    queryKey: ["map-image-layers", rasterIds.join(",")],
    enabled: rasterIds.length > 0,
    queryFn: async () => {
      const fetched = await Promise.all(
        rasterIds.map(async (id) => {
          try {
            const info = await fetchSourcePreview(id);
            const item = sources?.items.find((entry) => entry.source_id === id);
            const kind = item?.kind ?? "drone_ori";
            const synthetic = item?.is_synthetic ?? false;
            const { role, hex } = mapRole(synthetic, kind);
            return {
              id,
              label: info.name,
              url: previewPngUrl(id),
              bounds: info.bounds,
              meta: `${kindLabel(kind)} · raster preview · ${info.width}×${info.height} px`,
              color: hex,
              role,
              synthetic,
            } satisfies PreviewLayer;
          } catch {
            return null;
          }
        }),
      );
      return fetched.filter(
        (layer): layer is PreviewLayer => layer !== null,
      );
    },
  });

  const rows = useMemo<LayerRow[]>(() => {
    const registryRows: LayerRow[] = (registryLayers ?? []).map((layer) => ({
      key: layer.id,
      label: layer.label,
      meta: layer.meta,
      group: "Registry" as const,
      role: layer.role,
      defaultOn: !layer.synthetic,
    }));
    const imageRows: LayerRow[] = (imageLayers ?? []).map((layer) => ({
      key: layer.id,
      label: layer.label,
      meta: layer.meta,
      group: "Registry" as const,
      role: layer.role,
      raster: true,
      defaultOn: !layer.synthetic,
    }));
    return [...LAYERS, ...registryRows, ...imageRows];
  }, [registryLayers, imageLayers]);

  /** Explicit on/off wins; otherwise a layer falls back to its default
   * (synthetic demo layers start hidden so the first view is real data). */
  const resolvedVisible = useMemo(() => {
    const resolved: Record<string, boolean> = {};
    for (const layer of rows) resolved[layer.key] = visible[layer.key] ?? layer.defaultOn;
    return resolved;
  }, [rows, visible]);

  const colorOf = (key: string): string | undefined =>
    (registryLayers ?? []).find((layer) => layer.id === key)?.color ??
    (imageLayers ?? []).find((layer) => layer.id === key)?.color;

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(
      (layer) =>
        layer.label.toLowerCase().includes(needle) || layer.meta.toLowerCase().includes(needle),
    );
  }, [rows, query]);

  const shownCount = rows.filter((layer) => resolvedVisible[layer.key]).length;
  const hiddenSynthetic = rows.filter(
    (layer) => layer.role === "synthetic" && !resolvedVisible[layer.key],
  ).length;

  const fitBounds = useMemo(() => {
    const boxes: ([number, number, number, number] | null)[] = [
      ...(registryLayers ?? []).map((layer) => layer.bbox),
      ...(imageLayers ?? []).map((layer) => layer.bounds),
    ];
    const valid = boxes.filter(
      (box): box is [number, number, number, number] => box !== null,
    );
    if (valid.length === 0) return null;
    let [minx, miny, maxx, maxy] = SECTOR22_BBOX;
    for (const [a, b, c, d] of valid) {
      if (a < minx) minx = a;
      if (b < miny) miny = b;
      if (c > maxx) maxx = c;
      if (d > maxy) maxy = d;
    }
    return [minx, miny, maxx, maxy] as [number, number, number, number];
  }, [registryLayers, imageLayers]);

  function toggle(key: string) {
    setVisible((current) => ({ ...current, [key]: !(current[key] ?? true) }));
  }

  return (
    <>
      <header style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "end", justifyContent: "space-between" }}>
        <div>
          <p className="label" style={{ color: "var(--text-muted)", margin: "0 0 4px" }}>
            Workbench
          </p>
          <h1 className="h1" style={{ margin: 0 }}>
            Chandigarh · Sector 22
          </h1>
        </div>
        <p className="small" style={{ margin: 0, color: "var(--text-muted)", maxWidth: "56ch" }}>
          Storage CRS EPSG:32643 (WGS 84 / UTM 43N). Basemap is Esri World Imagery (attribution on
          the map); registered vector layers load from the API under “Registry layers”, and OSM
          stays as an alternative basemap.
        </p>
      </header>

      <nav className="flow-strip" aria-label="Pipeline: upload data, auto-harmonize, result">
        {FLOW.map((item, index) => (
          <span key={item.step} className="flow-step">
            {index > 0 && (
              <ArrowRight className="flow-arrow" size={16} aria-hidden="true" />
            )}
            <a href={item.href} className="flow-link">
              <span className="data flow-num">{item.step}</span>
              <span>
                <strong>{item.label}</strong>
                <span className="small" style={{ display: "block", color: "var(--text-muted)" }}>
                  {item.hint}
                </span>
              </span>
            </a>
          </span>
        ))}
      </nav>

      <div className="wb-toolbar">
        <div className="wb-tabs" role="tablist" aria-label="Workbench panes">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "layers"}
            className={tab === "layers" ? "wb-tab is-active" : "wb-tab"}
            onClick={() => setTab("layers")}
          >
            Layers
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "map"}
            className={tab === "map" ? "wb-tab is-active" : "wb-tab"}
            onClick={() => setTab("map")}
          >
            Map
          </button>
        </div>

        <span className="small" style={{ color: "var(--text-muted)" }}>
          {shownCount} of {rows.length} layers visible
        </span>

        <button
          type="button"
          className="btn btn--secondary"
          style={{ minHeight: "32px", padding: "0 12px", fontSize: "13px" }}
          onClick={() => setFitKey((key) => key + 1)}
        >
          Fit extent
        </button>

        <span className="small wb-hint">
          Split compare, offset arrows and the conflict hatch arrive with the matched vector tiles
          (Stage 4) — nothing is drawn from invented geometry.
        </span>
      </div>

      <div className={`wb ${tab === "layers" ? "show-layers" : ""}`}>
        <aside className="panel wb-layers" aria-label="Layers">
          <label className="wb-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search layers"
              aria-label="Search layers"
            />
          </label>

          {GROUPS.map((group) => {
            const groupRows = filtered.filter((layer) => layer.group === group);
            if (groupRows.length === 0) return null;
            return (
              <section key={group} style={{ marginBottom: "14px" }}>
                <h2 className="label" style={{ margin: "0 0 6px", color: "var(--text-muted)" }}>
                  {group} ({groupRows.length})
                </h2>
                <div style={{ display: "grid", gap: "2px" }}>
                  {groupRows.map((layer) => (
                    <div
                      key={layer.key}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "26px minmax(0, 1fr)",
                        alignItems: "start",
                        gap: "8px",
                        padding: "8px 6px",
                        borderRadius: "var(--radius-control)",
                        background: resolvedVisible[layer.key] ? "var(--paper-200)" : "transparent",
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => toggle(layer.key)}
                        aria-pressed={resolvedVisible[layer.key]}
                        aria-label={`${resolvedVisible[layer.key] ? "Hide" : "Show"} ${layer.label}`}
                        title={resolvedVisible[layer.key] ? "Hide layer" : "Show layer"}
                        style={{
                          display: "grid",
                          placeItems: "center",
                          width: "26px",
                          height: "26px",
                          border: "1px solid var(--border)",
                          borderRadius: "var(--radius-control)",
                          background: "var(--paper-50)",
                          cursor: "pointer",
                          color: "var(--text)",
                        }}
                      >
                        {resolvedVisible[layer.key] ? <Eye size={14} /> : <EyeOff size={14} />}
                      </button>
                      <span style={{ minWidth: 0 }}>
                        <span
                          className="small"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            fontWeight: 500,
                            opacity: resolvedVisible[layer.key] ? 1 : 0.55,
                          }}
                        >
                          <LayerPreview
                            layer={layer.key}
                            raster={layer.raster}
                            color={colorOf(layer.key)}
                          />
                          {layer.label}
                        </span>
                        <span
                          className="small"
                          style={{
                            display: "block",
                            color: "var(--text-muted)",
                            marginTop: "2px",
                          }}
                        >
                          {layer.meta}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}

          <div className="divider" style={{ margin: "4px 0 12px" }} />

          <h2 className="label" style={{ margin: "0 0 8px", color: "var(--text-muted)" }}>
            Legend — what each colour means
          </h2>
          <div style={{ display: "grid", gap: "12px" }}>
            {LEGEND_GROUPS.map(({ role, title, note }) => {
              const entries = rows.filter(
                (layer) => layer.role === role && resolvedVisible[layer.key],
              );
              if (entries.length === 0) return null;
              return (
                <section key={role}>
                  <p className="small" style={{ margin: "0 0 2px", fontWeight: 600 }}>
                    {title}
                  </p>
                  <p
                    className="small"
                    style={{ margin: "0 0 6px", color: "var(--text-muted)" }}
                  >
                    {note}
                  </p>
                  <ul
                    style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "4px" }}
                  >
                    {entries.map((layer) => (
                      <li
                        key={layer.key}
                        className="small"
                        style={{ display: "flex", alignItems: "center", gap: "8px" }}
                      >
                        <LayerPreview
                          layer={layer.key}
                          raster={layer.raster}
                          color={colorOf(layer.key)}
                        />
                        {layer.label}
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
            {hiddenSynthetic > 0 && (
              <p className="small" style={{ margin: 0, color: "var(--text-muted)" }}>
                {hiddenSynthetic} synthetic layer{hiddenSynthetic > 1 ? "s" : ""} hidden — use the
                eye icons above to show demo data.
              </p>
            )}
          </div>
        </aside>

        <section className="panel wb-map" aria-label="Map of Sector 22, Chandigarh">
        <MapCanvas
          visible={resolvedVisible}
          fitKey={fitKey}
          dynamicLayers={registryLayers ?? []}
          imageLayers={imageLayers ?? []}
          fitBounds={fitBounds}
        />
          <div className="wb-hud">
            <span className="label" style={{ color: "var(--text)" }}>
              Sector 22 extent
            </span>
            <span className="small" style={{ color: "var(--text-muted)" }}>
              Tilted view · drag to orbit, right-drag to tilt
            </span>
          </div>
        </section>
      </div>

      <style>{`
        .flow-strip {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px 4px;
          margin-top: 16px;
          padding: 10px 14px;
          border: 1px solid var(--border);
          border-radius: var(--radius-panel);
          background: var(--paper-100);
        }
        .flow-step { display: inline-flex; align-items: center; gap: 4px; }
        .flow-arrow { color: var(--text-muted); flex: none; }
        .flow-link {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 4px 10px;
          border-radius: var(--radius-control);
          color: var(--text);
          text-decoration: none;
        }
        .flow-link:hover { background: var(--marigold-100); }
        .flow-num { color: var(--layer-conflict); font-weight: 600; }
        .wb-toolbar {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 10px 14px;
          margin-top: 16px;
          padding: 8px 10px;
          border: 1px solid var(--border);
          border-radius: var(--radius-panel);
          background: var(--paper-100);
        }
        .wb-tabs { display: flex; gap: 4px; }
        .wb-tab {
          font: inherit;
          font-size: 12px;
          padding: 4px 10px;
          border: 1px solid var(--border);
          border-radius: var(--radius-control);
          background: var(--paper-50);
          color: var(--text-muted);
          cursor: pointer;
        }
        .wb-tab.is-active {
          background: var(--marigold-100);
          border-color: var(--border-ctl);
          color: var(--text);
          font-weight: 600;
        }
        .wb-hint { flex: 1 1 260px; min-width: 0; }
        .wb-search {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 8px;
          margin-bottom: 12px;
          border: 1px solid var(--border);
          border-radius: var(--radius-control);
          background: var(--paper-50);
          color: var(--text-muted);
        }
        .wb-search input {
          flex: 1;
          min-width: 0;
          border: 0;
          outline: 0;
          background: transparent;
          font: inherit;
          font-size: 13px;
          color: var(--text);
        }
        .wb {
          display: grid;
          gap: 12px;
          margin-top: 12px;
        }
        .wb-layers { display: none; padding: 12px; }
        .wb-map { position: relative; overflow: hidden; height: 60vh; min-height: 320px; }
        .wb.show-layers .wb-layers { display: block; }
        .wb.show-layers .wb-map { display: none; }
        .wb-hud {
          position: absolute;
          top: 10px;
          left: 10px;
          display: grid;
          gap: 2px;
          padding: 7px 10px;
          border: 1px solid var(--border);
          border-radius: var(--radius-control);
          background: color-mix(in srgb, var(--paper-50) 92%, transparent);
          box-shadow: var(--shadow-popover);
          pointer-events: none;
        }
        @media (min-width: 960px) {
          .wb {
            grid-template-columns: 320px minmax(0, 1fr);
            height: calc(100vh - 260px);
            min-height: 470px;
          }
          .wb-layers, .wb-map { display: block !important; height: auto; }
          .wb-layers { overflow: auto; }
          .wb-tabs { display: none; }
        }
      `}</style>
    </>
  );
}
