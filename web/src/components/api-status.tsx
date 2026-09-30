"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchReadiness, type Readiness, type ServiceCheck } from "@/lib/api";

type CheckKey = keyof Readiness["checks"];

const CHECK_LABELS: Record<CheckKey, string> = {
  database: "PostgreSQL + PostGIS",
  redis: "Redis (job queue)",
  object_store: "MinIO object store",
  policy: "NAKSHA policy file",
};

function checkDetail(key: CheckKey, check: ServiceCheck): string {
  if (!check.ok) return check.error ?? "unavailable";
  if (key === "database") {
    const detail = check as Readiness["checks"]["database"];
    return detail.postgis_version ? `PostGIS ${detail.postgis_version}` : "reachable";
  }
  if (key === "object_store") {
    const detail = check as Readiness["checks"]["object_store"];
    return detail.bucket ? `bucket "${detail.bucket}"` : "reachable";
  }
  if (key === "policy") {
    const detail = check as Readiness["checks"]["policy"];
    return detail.name ? `${detail.name} v${detail.version ?? "?"}` : "reachable";
  }
  return "reachable";
}

export function ApiStatus() {
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ["readyz"],
    queryFn: () => fetchReadiness(),
    retry: 1,
  });

  return (
    <section className="panel" aria-labelledby="service-readiness-heading">
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "16px",
          padding: "16px 20px",
        }}
      >
        <h2 id="service-readiness-heading" className="h2" style={{ margin: 0 }}>
          Service readiness
        </h2>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          {isFetching ? "Checking…" : "Re-check"}
        </button>
      </div>

      <div className="divider" />

      <div style={{ padding: "8px 20px 16px" }} aria-live="polite">
        {isPending && (
          <p className="small" style={{ color: "var(--text-muted)", margin: "8px 0 0" }}>
            Contacting the API at{" "}
            <span className="data">{`${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/readyz`}</span>
            …
          </p>
        )}

        {error && (
          <p className="small" style={{ color: "var(--chilli-600)", margin: "8px 0 0" }}>
            Error: {error instanceof Error ? error.message : "request failed"}. Start the stack with{" "}
            <span className="data">docker compose up -d</span>.
          </p>
        )}

        {data && (
          <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <caption className="label" style={{ textAlign: "left", padding: "4px 0 8px" }}>
              {data.service} v{data.version}: {data.status.replace("_", " ")}
            </caption>
            <thead>
              <tr>
                <th scope="col" className="label" style={{ textAlign: "left", paddingBottom: "6px" }}>
                  Dependency
                </th>
                <th scope="col" className="label" style={{ textAlign: "left", paddingBottom: "6px" }}>
                  Status
                </th>
                <th scope="col" className="label" style={{ textAlign: "left", paddingBottom: "6px" }}>
                  Detail
                </th>
              </tr>
            </thead>
            <tbody>
              {(Object.keys(CHECK_LABELS) as CheckKey[]).map((key) => {
                const check = data.checks[key];
                return (
                  <tr key={key} style={{ borderTop: "1px solid var(--border)" }}>
                    <th scope="row" style={{ textAlign: "left", fontWeight: 500, padding: "8px 12px 8px 0" }}>
                      {CHECK_LABELS[key]}
                    </th>
                    <td style={{ padding: "8px 12px 8px 0" }}>
                      <span className="stamp" style={{ color: check.ok ? "var(--paddy-600)" : "var(--chilli-600)" }}>
                        {check.ok ? "OK" : "DOWN"}
                      </span>
                    </td>
                    <td className="data" style={{ padding: "8px 0", color: "var(--text-muted)" }}>
                      {checkDetail(key, check)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </section>
  );
}
