"""conflict and conflict_decision

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30

Plan Stage 6, first slice. `conflict` holds one detected geometric disagreement between
two loaded sources (backend.md §4); `conflict_decision` is the append-only decision log
(backend.md §5.6). Rows are keyed by the source pair plus both feature ids, so
re-running detection replaces only rows still in the queue and never touches a decision.
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _storage_srid() -> int:
    return int(os.environ.get("STORAGE_SRID", "32643"))


def upgrade() -> None:
    srid = _storage_srid()

    op.execute(
        f"""
        CREATE TABLE conflict (
            conflict_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_a uuid NOT NULL REFERENCES source_registry (source_id) ON DELETE CASCADE,
            source_b uuid NOT NULL REFERENCES source_registry (source_id) ON DELETE CASCADE,
            fid_a text NOT NULL,
            fid_b text NOT NULL,
            type text NOT NULL,
            severity text NOT NULL,
            state text NOT NULL DEFAULT 'queue',
            area_m2 double precision,
            outside_m double precision,
            reason text NOT NULL,
            geom geometry(Geometry, {srid}),
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_a, source_b, fid_a, fid_b)
        )
        """
    )
    op.execute("CREATE INDEX ix_conflict_state ON conflict (state)")
    op.execute("CREATE INDEX ix_conflict_geom ON conflict USING gist (geom)")

    op.execute(
        """
        CREATE TABLE conflict_decision (
            decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            conflict_id uuid NOT NULL REFERENCES conflict (conflict_id) ON DELETE CASCADE,
            actor text NOT NULL,
            action text NOT NULL,
            reason_code text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_conflict_decision_conflict ON conflict_decision (conflict_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conflict_decision")
    op.execute("DROP TABLE IF EXISTS conflict")
