"use client";

import { useMemo, useState } from "react";

import { ArrowRight, Eye, EyeOff, Search } from "lucide-react";

import { MapCanvas, type LayerVisibility } from "@/components/map-canvas";

type LayerKey = keyof LayerVisibility;
type LayerGroup = "Basemap" | "Overlays";

interface LayerRow {
  key: LayerKey;
  label: string;
  meta: string;
  group: LayerGroup;
}

const LAYERS: LayerRow[] = [
  {
    key: "satellite",
    label: "Satellite imagery",
    meta: "Raster · Tiles © Esri, Maxar, Earthstar Geographics",
    group: "Basemap",
  },
  {
    key: "osm",
    label: "OSM basemap",
    meta: "Raster · © OpenStreetMap contributors, ODbL 1.0",
    group: "Basemap",
  },
  {
    key: "boundary",
    label: "Sector 22 boundary",
    meta: "Municipal · OSM relation 7894503 · 2026-09-30",
    group: "Overlays",
  },
  {
    key: "roads",
    label: "Sector 22 roads",
    meta: "Municipal · 494 ways · ODbL 1.0",
    group: "Overlays",
  },
];

const GROUPS: LayerGroup[] = ["Basemap", "Overlays"];

const FLOW = [
  { step: "01", label: "Upload data", hint: "Register & load", href: "/sources" },
  { step: "02", label: "Auto-harmonize", hint: "CRS fit · QC flags", href: "/queue/conflicts" },
  { step: "03", label: "Result", hint: "Layers & queue", href: "/map" },
] as const;

function LayerPreview({ layer }: { layer: LayerKey }) {
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
  if (layer === "satellite") {
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

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return LAYERS;
    return LAYERS.filter(
      (layer) =>
        layer.label.toLowerCase().includes(needle) || layer.meta.toLowerCase().includes(needle),
    );
  }, [query]);

  const shownCount = LAYERS.filter((layer) => visible[layer.key]).length;

  function toggle(key: LayerKey) {
    setVisible((current) => ({ ...current, [key]: !current[key] }));
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
          the map); ORI drone imagery is not ingested yet, and OSM stays as an alternative basemap.
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
          {shownCount} of {LAYERS.length} layers visible
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
            const rows = filtered.filter((layer) => layer.group === group);
            if (rows.length === 0) return null;
            return (
              <section key={group} style={{ marginBottom: "14px" }}>
                <h2 className="label" style={{ margin: "0 0 6px", color: "var(--text-muted)" }}>
                  {group} ({rows.length})
                </h2>
                <div style={{ display: "grid", gap: "2px" }}>
                  {rows.map((layer) => (
                    <div
                      key={layer.key}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "26px minmax(0, 1fr)",
                        alignItems: "start",
                        gap: "8px",
                        padding: "8px 6px",
                        borderRadius: "var(--radius-control)",
                        background: visible[layer.key] ? "var(--paper-200)" : "transparent",
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => toggle(layer.key)}
                        aria-pressed={visible[layer.key]}
                        aria-label={`${visible[layer.key] ? "Hide" : "Show"} ${layer.label}`}
                        title={visible[layer.key] ? "Hide layer" : "Show layer"}
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
                        {visible[layer.key] ? <Eye size={14} /> : <EyeOff size={14} />}
                      </button>
                      <span style={{ minWidth: 0 }}>
                        <span
                          className="small"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            fontWeight: 500,
                            opacity: visible[layer.key] ? 1 : 0.55,
                          }}
                        >
                          <LayerPreview layer={layer.key} />
                          {layer.label}
                        </span>
                        <span
                          className="small"
                          style={{ display: "block", color: "var(--text-muted)", marginTop: "2px" }}
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
            Legend
          </h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "6px" }}>
            <li className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                aria-hidden="true"
                style={{ width: "18px", height: "3px", background: "var(--layer-municipal)" }}
              />
              Road centreline (municipal)
            </li>
            <li className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                aria-hidden="true"
                style={{ width: "18px", height: "3px", background: "var(--layer-conflict)" }}
              />
              Administrative boundary (municipal)
            </li>
          </ul>
        </aside>

        <section className="panel wb-map" aria-label="Map of Sector 22, Chandigarh">
          <MapCanvas visible={visible} fitKey={fitKey} />
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
