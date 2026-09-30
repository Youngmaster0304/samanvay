import { EmptyState } from "@/components/empty-state";

export default function ChangesPage() {
  return (
    <>
      <p className="label" style={{ color: "var(--text-muted)", margin: "0 0 4px" }}>
        Change detection
      </p>
      <h1 className="h1" style={{ margin: "0 0 20px" }}>
        Change log
      </h1>

      <EmptyState
        title="No changes detected yet"
        body="Detected changes (new, removed, moved, modified, split, merged, encroachment candidates) are recorded after two vintages of the same area have been matched. This deployment has one vintage registered, so there is nothing to list."
        actionLabel="Open the source registry"
        actionHref="/sources"
        note="every entry here is append-only and cites both source ids and the rule that fired"
      />
    </>
  );
}
