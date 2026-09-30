"""source_feature and transform_log

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30

Stage 3 (CRS engine). `source_feature` holds one observation per source feature in the
storage CRS chosen for the AOI; `transform_log` records every CRS or rubber-sheet step
with its parameters and residuals (backend.md §4 and §5.2).

The storage SRID is read from the same setting the application uses, so the migration
and the running API cannot disagree about the target CRS.
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _storage_srid() -> int:
    return int(os.environ.get("STORAGE_SRID", "32643"))


def upgrade() -> None:
    srid = _storage_srid()

    op.execute(
        f"""
        CREATE TABLE source_feature (
            obs_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id uuid NOT NULL REFERENCES source_registry (source_id) ON DELETE CASCADE,
            source_fid text NOT NULL,
            feature_class text NOT NULL,
            geom geometry(Geometry, {srid}) NOT NULL,
            raw_props jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            extractor_conf double precision,
            qc_flags text[] NOT NULL DEFAULT '{{}}',
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_id, source_fid)
        )
        """
    )
    op.execute("CREATE INDEX ix_source_feature_geom ON source_feature USING gist (geom)")
    op.execute("CREATE INDEX ix_source_feature_class ON source_feature (feature_class)")

    op.execute(
        """
        CREATE TABLE transform_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id uuid NOT NULL REFERENCES source_registry (source_id) ON DELETE CASCADE,
            pipeline text NOT NULL,
            n_control integer,
            rmse_m double precision,
            max_resid_m double precision,
            params jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_transform_log_source ON transform_log (source_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transform_log")
    op.execute("DROP TABLE IF EXISTS source_feature")
