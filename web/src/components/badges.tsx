import { KIND_COLORS, kindLabel } from "@/lib/sources";

/**
 * Status, grade and synthetic badges (docs/front.md §5).
 * Colour is never the only signal: every badge carries its word or letter.
 */

export type ReviewStatus =
  | "auto-resolved"
  | "accepted"
  | "needs-review"
  | "dispute"
  | "rejected";

const STATUS_STYLE: Record<ReviewStatus, { label: string; color: string }> = {
  "auto-resolved": { label: "Auto-resolved", color: "var(--status-auto-resolved)" },
  accepted: { label: "Accepted", color: "var(--status-accepted)" },
  "needs-review": { label: "Needs review", color: "var(--status-needs-review)" },
  dispute: { label: "Dispute", color: "var(--status-dispute)" },
  rejected: { label: "Rejected", color: "var(--status-rejected)" },
};

export function StatusChip({ status }: { status: ReviewStatus }) {
  const { label, color } = STATUS_STYLE[status];
  return (
    <span className="stamp" style={{ color }}>
      {label}
    </span>
  );
}

const GRADE_COLOR: Record<string, string> = {
  A: "var(--grade-a)",
  B: "var(--grade-b)",
  C: "var(--grade-c)",
  D: "var(--grade-d)",
  E: "var(--grade-e)",
};

export function GradeBadge({ grade, score }: { grade: string; score?: number | null }) {
  const color = GRADE_COLOR[grade] ?? "var(--text-muted)";
  return (
    <span
      className="stamp"
      style={{ color, borderColor: color, display: "inline-flex", gap: "6px", alignItems: "baseline" }}
      title={`Confidence grade ${grade}`}
    >
      <span aria-hidden="true" style={{ fontSize: "13px", fontWeight: 700 }}>
        {grade}
      </span>
      <span>Grade {grade}</span>
      {typeof score === "number" && <span className="data">{score.toFixed(3)}</span>}
    </span>
  );
}

export function SyntheticBadge() {
  return (
    <span
      className="stamp"
      style={{
        background: "var(--paper-100)",
        color: "var(--ink-900)",
        borderColor: "var(--ink-900)",
        textDecoration: "line-through",
      }}
      title="This dataset was generated for testing. It is not evidence about real parcels."
    >
      Synthetic
    </span>
  );
}

export function KindTag({ kind }: { kind: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
      <span
        aria-hidden="true"
        style={{
          width: "10px",
          height: "10px",
          borderRadius: "2px",
          background: KIND_COLORS[kind] ?? "var(--stone-500)",
          border: "1px solid var(--ink-900)",
        }}
      />
      <span>{kindLabel(kind)}</span>
    </span>
  );
}
