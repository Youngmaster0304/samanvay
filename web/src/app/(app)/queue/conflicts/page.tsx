"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import {
  decideConflict,
  detectConflicts,
  fetchConflicts,
  formatArea,
  formatLength,
  SEVERITY_COLOR,
  STATE_LABEL,
  TYPE_LABEL,
  type Conflict,
  type ConflictAction,
  type DetectResult,
} from "@/lib/conflicts";
import { fetchSources } from "@/lib/sources";

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
  padding: "10px 12px 10px 0",
  verticalAlign: "top",
  borderBottom: "1px solid var(--border-ctl)",
};

const FIELD: React.CSSProperties = {
  minHeight: "36px",
  padding: "0 8px",
  border: "1px solid var(--border-ctl)",
  borderRadius: "var(--radius-control)",
  background: "var(--surface)",
  color: "var(--text)",
  font: "inherit",
};

const ACTIONS: { action: ConflictAction; label: string }[] = [
  { action: "accept_a", label: "Accept A" },
  { action: "accept_b", label: "Accept B" },
  { action: "defer", label: "Defer" },
  { action: "reject", label: "Dismiss" },
];

function severityStamp(conflict: Conflict) {
  return (
    <span className="stamp" style={{ color: SEVERITY_COLOR[conflict.severity] }}>
      {conflict.severity === "high" ? "High" : conflict.severity === "medium" ? "Medium" : "Low"}
    </span>
  );
}

export default function ConflictsPage() {
  const queryClient = useQueryClient();
  const [stateFilter, setStateFilter] = useState("queue");
  const [typeFilter, setTypeFilter] = useState("");
  const [sourceA, setSourceA] = useState("");
  const [sourceB, setSourceB] = useState("");
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["sources"],
    queryFn: () => fetchSources(),
    retry: 1,
  });

  const conflictsQuery = useQuery({
    queryKey: ["conflicts", stateFilter, typeFilter],
    queryFn: () =>
      fetchConflicts({
        state: stateFilter || undefined,
        type: typeFilter || undefined,
      }),
    retry: 1,
  });

  const detect = useMutation({
    mutationFn: () => detectConflicts(sourceA, sourceB),
    onSuccess: (result) => {
      setDetectResult(result);
      void queryClient.invalidateQueries({ queryKey: ["conflicts"] });
    },
  });

  const decide = useMutation({
    mutationFn: (variables: { conflict_id: string; action: ConflictAction; reason_code: string }) =>
      decideConflict(variables.conflict_id, variables.action, variables.reason_code),
    onSuccess: () => {
      setDecisionError(null);
      void queryClient.invalidateQueries({ queryKey: ["conflicts"] });
    },
    onError: (error: Error) => setDecisionError(error.message),
  });

  const loaded = (sourcesQuery.data?.items ?? []).filter(
    (source) => source.has_geometry && (source.feature_count ?? 0) > 0,
  );
  const candidates = loaded.length >= 2;

  const items = conflictsQuery.data?.items ?? [];
  const severityCounts = items.reduce<Record<string, number>>((acc, item) => {
    acc[item.severity] = (acc[item.severity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          alignItems: "baseline",
          justifyContent: "space-between",
        }}
      >
        <div>
          <p className="label" style={{ color: "var(--text-muted)", margin: "0 0 4px" }}>
            Review
          </p>
          <h1 className="h1" style={{ margin: "0 0 4px" }}>
            Conflict queue
          </h1>
        </div>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => void conflictsQuery.refetch()}
          disabled={conflictsQuery.isFetching}
        >
          {conflictsQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <p
        className="small"
        style={{ color: "var(--text-muted)", margin: "0 0 16px", maxWidth: "78ch" }}
      >
        A conflict is a measured geometric disagreement between two loaded sources — an overlap
        area or a length of line outside the other feature. Severities come from the{" "}
        <span className="data">conflicts:</span> block in the policy file; nothing here is a
        legal determination, and every decision waits for a reviewer.
      </p>

      <div className="panel" style={{ padding: "14px 16px", marginBottom: "16px" }}>
        <p className="label" style={{ margin: "0 0 10px", color: "var(--text-muted)" }}>
          Run detection
        </p>
        {sourcesQuery.isPending && (
          <p className="small" style={{ color: "var(--text-muted)" }}>
            Contacting <span className="data">GET /sources</span>…
          </p>
        )}
        {sourcesQuery.error && (
          <p className="small" style={{ color: "var(--chilli-600)" }}>
            Cannot reach the source registry:{" "}
            {sourcesQuery.error instanceof Error ? sourcesQuery.error.message : "request failed"}.
          </p>
        )}
        {sourcesQuery.data && !candidates && (
          <p className="small" style={{ color: "var(--text-muted)" }}>
            Detection needs two sources with loaded features; this deployment has{" "}
            {loaded.length}.{" "}
            <a href="/sources">Register and load</a> another source to compare.
          </p>
        )}
        {candidates && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
            <label className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              Source A
              <select value={sourceA} onChange={(event) => setSourceA(event.target.value)} style={FIELD}>
                <option value="">Choose…</option>
                {loaded.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {source.name} ({source.feature_count} features)
                  </option>
                ))}
              </select>
            </label>
            <label className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              Source B
              <select value={sourceB} onChange={(event) => setSourceB(event.target.value)} style={FIELD}>
                <option value="">Choose…</option>
                {loaded.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {source.name} ({source.feature_count} features)
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!sourceA || !sourceB || sourceA === sourceB || detect.isPending}
              onClick={() => detect.mutate()}
            >
              {detect.isPending ? "Comparing…" : "Detect conflicts"}
            </button>
            {detect.isError && (
              <span className="small" style={{ color: "var(--chilli-600)" }}>
                {detect.error instanceof Error ? detect.error.message : "detection failed"}
              </span>
            )}
          </div>
        )}
        {detectResult && (
          <p className="small" style={{ margin: "10px 0 0", color: "var(--text)" }}>
            <span className="data">{detectResult.pairs_examined}</span> intersecting pair
            {detectResult.pairs_examined === 1 ? "" : "s"} examined between “
            {detectResult.source_a_name}” and “{detectResult.source_b_name}”;{" "}
            <strong>
              {detectResult.created} new conflict{detectResult.created === 1 ? "" : "s"}
            </strong>{" "}
            queued
            {Object.keys(detectResult.by_severity).length > 0 &&
              ` (${Object.entries(detectResult.by_severity)
                .map(([severity, count]) => `${count} ${severity}`)
                .join(", ")})`}
            . Policy <span className="data">{detectResult.policy.name}</span> v
            <span className="data">{detectResult.policy.version}</span>.
          </p>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "10px",
          alignItems: "center",
          marginBottom: "14px",
        }}
      >
        <label className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          State
          <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)} style={FIELD}>
            <option value="queue">In queue</option>
            <option value="resolved">Resolved</option>
            <option value="deferred">Deferred</option>
            <option value="dismissed">Dismissed</option>
            <option value="">All</option>
          </select>
        </label>
        <label className="small" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          Type
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} style={FIELD}>
            <option value="">All types</option>
            <option value="overlap">Overlap</option>
            <option value="boundary_crossing">Boundary crossing</option>
          </select>
        </label>
        {conflictsQuery.data && (
          <span className="data" style={{ color: "var(--text-muted)" }}>
            {items.length} shown
            {stateFilter === "queue" &&
              Object.entries(severityCounts)
                .map(([severity, count]) => ` · ${count} ${severity}`)
                .join("")}
          </span>
        )}
      </div>

      {conflictsQuery.isPending && (
        <p className="small" style={{ color: "var(--text-muted)" }}>
          Contacting <span className="data">GET /conflicts</span>…
        </p>
      )}

      {conflictsQuery.error && (
        <EmptyState
          title="Cannot reach the conflict service"
          body={`GET /conflicts failed: ${
            conflictsQuery.error instanceof Error ? conflictsQuery.error.message : "request failed"
          }. The queue lives in the API, so the stack has to be running.`}
          note="docker compose up -d   # then Refresh"
        />
      )}

      {conflictsQuery.data && items.length === 0 && (
        <EmptyState
          title={stateFilter === "queue" ? "No conflicts in the queue" : "No conflicts match this filter"}
          body={
            stateFilter === "queue"
              ? "Nothing has been detected (or every conflict has been decided) for the current source pairs. Run detection above with two loaded sources to compare them; the queue only ever shows what PostGIS actually measured."
              : "The registry of detected conflicts has no row with this state and type right now."
          }
          actionLabel="Back to the queue"
          actionHref="/queue/conflicts"
        />
      )}

      {conflictsQuery.data && items.length > 0 && (
        <div className="panel" style={{ overflowX: "auto", padding: "12px 16px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <caption
              className="label"
              style={{ textAlign: "left", padding: "0 0 10px", color: "var(--text-muted)" }}
            >
              {conflictsQuery.data.total} conflict{conflictsQuery.data.total === 1 ? "" : "s"}, newest
              first
            </caption>
            <thead>
              <tr>
                <th scope="col" style={TH}>
                  Severity
                </th>
                <th scope="col" style={TH}>
                  Type
                </th>
                <th scope="col" style={TH}>
                  Sources
                </th>
                <th scope="col" style={TH}>
                  Measured
                </th>
                <th scope="col" style={{ ...TH, minWidth: "34ch" }}>
                  Why it is queued
                </th>
                <th scope="col" style={TH}>
                  Decision
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((conflict) => {
                const reason = reasons[conflict.conflict_id] ?? "";
                const pending = decide.isPending && decide.variables?.conflict_id === conflict.conflict_id;
                return (
                  <tr key={conflict.conflict_id}>
                    <td style={TD}>{severityStamp(conflict)}</td>
                    <td style={TD}>{TYPE_LABEL[conflict.type] ?? conflict.type}</td>
                    <td style={{ ...TD, whiteSpace: "nowrap" }}>
                      <div>
                        <span className="data">{conflict.fid_a}</span> in {conflict.source_a_name}
                      </div>
                      <div style={{ color: "var(--text-muted)" }}>
                        <span className="data">{conflict.fid_b}</span> in {conflict.source_b_name}
                      </div>
                    </td>
                    <td style={{ ...TD, whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
                      {conflict.type === "overlap"
                        ? formatArea(conflict.area_m2)
                        : formatLength(conflict.outside_m)}
                    </td>
                    <td style={TD}>{conflict.reason}</td>
                    <td style={{ ...TD, minWidth: "30ch" }}>
                      {conflict.state !== "queue" ? (
                        <span className="stamp" style={{ color: "var(--text-muted)" }}>
                          {STATE_LABEL[conflict.state]}
                        </span>
                      ) : (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                          <input
                            type="text"
                            value={reason}
                            onChange={(event) =>
                              setReasons((current) => ({
                                ...current,
                                [conflict.conflict_id]: event.target.value,
                              }))
                            }
                            placeholder="reason code"
                            aria-label={`Reason code for conflict ${conflict.fid_a} and ${conflict.fid_b}`}
                            style={{ ...FIELD, width: "132px" }}
                          />
                          {ACTIONS.map(({ action, label }) => (
                            <button
                              key={action}
                              type="button"
                              className="btn btn--secondary"
                              disabled={!reason.trim() || pending}
                              title={
                                action === "accept_a"
                                  ? `Accept source A (${conflict.source_a_name})`
                                  : action === "accept_b"
                                    ? `Accept source B (${conflict.source_b_name})`
                                    : label
                              }
                              onClick={() =>
                                decide.mutate({
                                  conflict_id: conflict.conflict_id,
                                  action,
                                  reason_code: reason.trim(),
                                })
                              }
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {decisionError && (
        <p className="small" style={{ color: "var(--chilli-600)", marginTop: "10px" }}>
          Decision refused: {decisionError}
        </p>
      )}
    </>
  );
}
