"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { ApiStatus } from "@/components/api-status";
import { SyntheticBadge } from "@/components/badges";
import { API_BASE } from "@/lib/api";
import { fetchSources, kindLabel } from "@/lib/sources";

const FLOW = [
  {
    step: "01",
    label: "Upload data",
    hint: "GeoJSON / GeoTIFF / CSV with licence, vintage, checksum",
    href: "/sources",
  },
  {
    step: "02",
    label: "Auto-harmonize",
    hint: "Reproject to EPSG:32643 · QC flags · conflicts & matches",
    href: "/queue/conflicts",
  },
  {
    step: "03",
    label: "Result",
    hint: "Satellite workbench, review queue, append-only decisions",
    href: "/map",
  },
] as const;

export default function OverviewPage() {
  const { data, error, isPending } = useQuery({
    queryKey: ["sources"],
    queryFn: () => fetchSources(),
    retry: 1,
  });

  const synthetic = data?.items.filter((item) => item.is_synthetic).length ?? 0;
  const byKind = new Map<string, number>();
  for (const item of data?.items ?? []) {
    byKind.set(item.kind, (byKind.get(item.kind) ?? 0) + 1);
  }
  const kinds = [...byKind.entries()].sort((a, b) => b[1] - a[1]);

  return (
    <>
      <h1 className="h1" style={{ margin: "8px 0 16px" }}>
        Harmonization workbench for urban land records
      </h1>

      <p className="lead" style={{ margin: "0 0 20px" }}>
        Samanvay aligns drone-derived, AI-extracted, cadastral, revenue, municipal, utility and GNSS
        layers over one coordinate frame, matches features across them, applies the NAKSHA three-tier
        reconciliation policy, and hands the cases it cannot settle to a reviewer with the evidence
        attached. Every score it prints carries the components it was built from.
      </p>

      <nav className="flow-strip" aria-label="Pipeline: upload data, auto-harmonize, result">
        {FLOW.map((item, index) => (
          <span key={item.step} className="flow-step">
            {index > 0 && <ArrowRight className="flow-arrow" size={18} aria-hidden="true" />}
            <Link href={item.href} className="flow-link">
              <span className="data flow-num">{item.step}</span>
              <span>
                <strong>{item.label}</strong>
                <span className="small" style={{ display: "block", color: "var(--text-muted)" }}>
                  {item.hint}
                </span>
              </span>
            </Link>
          </span>
        ))}
      </nav>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center", marginTop: "16px" }}>
        <Link className="btn btn--primary" href="/sources">
          Register a source
        </Link>
        <Link className="btn btn--secondary" href="/map">
          Open the workbench
        </Link>
        <a className="btn btn--secondary" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
          API reference
        </a>
        <span className="data" style={{ color: "var(--text-muted)" }}>
          {API_BASE}
        </span>
      </div>

      <style>{`
        .flow-strip {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px 4px;
          padding: 14px 18px;
          border: 1px solid var(--border);
          border-radius: var(--radius-panel);
          background: linear-gradient(90deg, var(--marigold-100) 0%, var(--paper-100) 70%);
        }
        .flow-step { display: inline-flex; align-items: center; gap: 6px; }
        .flow-arrow { color: var(--text-muted); flex: none; }
        .flow-link {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 6px 12px;
          border-radius: var(--radius-control);
          color: var(--text);
          text-decoration: none;
        }
        .flow-link:hover { background: color-mix(in srgb, var(--paper-50) 80%, transparent); }
        .flow-num { color: var(--layer-conflict); font-weight: 600; font-size: 15px; }
        .flow-link strong { font-size: 15px; letter-spacing: 0.01em; }
      `}</style>

      <div style={{ height: "32px" }} />

      <section className="panel" aria-labelledby="registry-heading" style={{ padding: "18px 20px" }}>
        <h2 id="registry-heading" className="h2" style={{ margin: "0 0 12px" }}>
          Registry
        </h2>

        {isPending && (
          <p className="small" style={{ color: "var(--text-muted)", margin: 0 }}>
            Contacting <span className="data">GET /sources</span>…
          </p>
        )}

        {error && (
          <p className="small" style={{ color: "var(--chilli-600)", margin: 0 }}>
            The registry API did not answer: {error instanceof Error ? error.message : "request failed"}.
            Start the stack with <span className="data">docker compose up -d</span>.
          </p>
        )}

        {data && (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "28px", marginBottom: "16px" }}>
              <Stat label="Sources registered" value={String(data.total)} />
              <Stat label="Real datasets" value={String(data.total - synthetic)} />
              <Stat
                label="Synthetic"
                value={String(synthetic)}
                suffix={synthetic > 0 ? <SyntheticBadge /> : undefined}
              />
              <Stat label="Distinct kinds" value={String(kinds.length)} />
            </div>

            <div className="divider" style={{ margin: "4px 0 12px" }} />

            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <caption className="label" style={{ textAlign: "left", padding: "0 0 8px", color: "var(--text-muted)" }}>
                Sources by kind
              </caption>
              <tbody>
                {kinds.map(([kind, count]) => (
                  <tr key={kind} style={{ borderTop: "1px solid var(--border)" }}>
                    <th scope="row" style={{ textAlign: "left", fontWeight: 500, padding: "8px 12px 8px 0" }}>
                      {kindLabel(kind)}
                    </th>
                    <td className="data" style={{ textAlign: "right", padding: "8px 0" }}>
                      {count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>

      <div style={{ height: "24px" }} />

      <section className="panel" aria-labelledby="status-heading" style={{ padding: "18px 20px", maxWidth: "640px" }}>
        <h2 id="status-heading" className="h2" style={{ margin: "0 0 8px" }}>
          Canonical features by status
        </h2>
        <p className="small" style={{ margin: 0, color: "var(--text-muted)" }}>
          No canonical layer has been produced in this deployment, so there are no counts to show:
          auto-resolved, accepted, needs review, dispute and rejected all read zero until matching and
          resolution run. The chart is deliberately left out rather than drawn with placeholder bars.
        </p>
        <p className="small" style={{ margin: "12px 0 0" }}>
          <Link href="/queue/conflicts">Open the conflict queue</Link> · <Link href="/changes">change log</Link>
        </p>
      </section>

      <div style={{ height: "24px" }} />

      <ApiStatus />

      <section style={{ marginTop: "24px", maxWidth: "68ch" }}>
        <h2 className="h2" style={{ margin: "0 0 8px" }}>
          What this run did not check
        </h2>
        <ul style={{ margin: 0, paddingLeft: "20px", display: "grid", gap: "6px" }}>
          <li>No legal title check and no ULPIN issue; ULPIN stays a linked field.</li>
          <li>ORI imagery, cadastral sheets, revenue records and utility maps are not ingested yet.</li>
          <li>
            Residual RMSE and coverage are not charted; per-source fit history and QC flags read
            from <span className="data">{"GET /sources/{id}/health"}</span>.
          </li>
          <li>Records of rights and rosters are synthetic unless a real, licensed copy is registered.</li>
        </ul>
      </section>
    </>
  );
}

function Stat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string;
  suffix?: React.ReactNode;
}) {
  return (
    <div>
      <p className="label" style={{ color: "var(--text-muted)", margin: "0 0 2px" }}>
        {label}
      </p>
      <p
        style={{
          margin: 0,
          fontFamily: "var(--font-stack-serif)",
          fontSize: "30px",
          lineHeight: "34px",
          fontVariantNumeric: "tabular-nums",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        {value}
        {suffix}
      </p>
    </div>
  );
}
