import Link from "next/link";

/**
 * Single-action empty state with no illustration (docs/front.md §5, §8).
 * Used wherever a backend endpoint does not exist yet, so the screen says what
 * is missing instead of showing invented rows.
 */
export function EmptyState({
  title,
  body,
  actionLabel,
  actionHref,
  note,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  actionHref?: string;
  note?: string;
}) {
  return (
    <section
      className="panel"
      style={{ padding: "32px 24px", textAlign: "left", maxWidth: "640px" }}
    >
      <h2 className="h2" style={{ margin: "0 0 8px" }}>
        {title}
      </h2>
      <p className="small" style={{ margin: "0 0 16px", color: "var(--text-muted)" }}>
        {body}
      </p>
      {actionLabel && actionHref && (
        <Link className="btn btn--primary" href={actionHref}>
          {actionLabel}
        </Link>
      )}
      {note && (
        <p className="data" style={{ margin: "16px 0 0", color: "var(--text-muted)" }}>
          {note}
        </p>
      )}
    </section>
  );
}
