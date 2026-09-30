/**
 * Conflict queue client. Mirrors `backend/app/api/conflicts.py` and the `conflict`
 * table in backend.md §4; every measurement shown in the UI comes from the API
 * (master prompt, non-negotiable rule 1).
 */

import { API_BASE } from "./api";

export type ConflictType = "overlap" | "boundary_crossing";
export type Severity = "high" | "medium" | "low";
export type ConflictState = "queue" | "resolved" | "deferred" | "dismissed";
export type ConflictAction = "accept_a" | "accept_b" | "defer" | "reject";

export interface Conflict {
  conflict_id: string;
  source_a: string;
  source_b: string;
  source_a_name: string;
  source_b_name: string;
  fid_a: string;
  fid_b: string;
  type: ConflictType;
  severity: Severity;
  state: ConflictState;
  area_m2: number | null;
  outside_m: number | null;
  reason: string;
  geometry: unknown | null;
  created_at: string;
}

export interface ConflictList {
  items: Conflict[];
  total: number;
}

export interface DetectResult {
  source_a: string;
  source_b: string;
  source_a_name: string;
  source_b_name: string;
  pairs_examined: number;
  created: number;
  by_severity: Partial<Record<Severity, number>>;
  by_type: Partial<Record<ConflictType, number>>;
  policy: { name: string; version: string; path: string; limits: Record<string, number> };
}

export interface DecisionResult {
  conflict_id: string;
  state: ConflictState;
  decision: {
    decision_id: string;
    actor: string;
    action: ConflictAction;
    reason_code: string;
    created_at: string;
  };
}

function base(): string {
  return API_BASE.replace(/\/$/, "");
}

export async function fetchConflicts(
  options: { state?: string; type?: string; limit?: number } = {},
): Promise<ConflictList> {
  const params = new URLSearchParams();
  if (options.state) params.set("state", options.state);
  if (options.type) params.set("type", options.type);
  params.set("limit", String(options.limit ?? 200));
  const response = await fetch(`${base()}/conflicts?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`GET /conflicts failed with ${response.status}`);
  }
  return (await response.json()) as ConflictList;
}

async function detailOf(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: { message?: string } | string };
    if (typeof body.detail === "string") return body.detail;
    return body.detail?.message ?? null;
  } catch {
    return null;
  }
}

export async function detectConflicts(source_a: string, source_b: string): Promise<DetectResult> {
  const response = await fetch(`${base()}/conflicts/detect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_a, source_b }),
  });
  if (!response.ok) {
    throw new Error(
      (await detailOf(response)) ?? `POST /conflicts/detect failed with ${response.status}`,
    );
  }
  return (await response.json()) as DetectResult;
}

export async function decideConflict(
  conflict_id: string,
  action: ConflictAction,
  reason_code: string,
  actor = "reviewer",
): Promise<DecisionResult> {
  const response = await fetch(`${base()}/conflicts/${conflict_id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reason_code, actor }),
  });
  if (!response.ok) {
    throw new Error(
      (await detailOf(response)) ?? `POST /conflicts/${conflict_id}/decision failed with ${response.status}`,
    );
  }
  return (await response.json()) as DecisionResult;
}

/** Severity is always shown as a word; colour is never the only signal (front.md §5). */
export const SEVERITY_COLOR: Record<Severity, string> = {
  high: "var(--chilli-600)",
  medium: "var(--status-needs-review)",
  low: "var(--text-muted)",
};

export const TYPE_LABEL: Record<ConflictType, string> = {
  overlap: "Overlap",
  boundary_crossing: "Boundary crossing",
};

export const STATE_LABEL: Record<ConflictState, string> = {
  queue: "In queue",
  resolved: "Resolved",
  deferred: "Deferred",
  dismissed: "Dismissed",
};

export function formatArea(area_m2: number | null): string {
  if (area_m2 === null) return "—";
  return `${area_m2.toLocaleString("en-IN", { maximumFractionDigits: 1 })} m²`;
}

export function formatLength(metres: number | null): string {
  if (metres === null) return "—";
  return `${metres.toLocaleString("en-IN", { maximumFractionDigits: 1 })} m`;
}
