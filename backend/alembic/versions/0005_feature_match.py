"""feature_match

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-30

Plan Stage 4, first slice. One row is an accepted 1-to-1 match between a polygon
feature of `source_a` and one of `source_b`, scored by intersection-over-union and
assigned greedily (Hungarian arrives with the scorer stage). Matches carry no
decision history yet, so a re-run replaces the pair's rows whole.
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE feature_match (
            match_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_a uuid NOT NULL REFERENCES source_registry (source_id) ON DELETE CASCADE,
            source_b uuid NOT NULL REFERENCES source_registry (source_id) ON DELETE CASCADE,
            fid_a text NOT NULL,
            fid_b text NOT NULL,
            score double precision NOT NULL,
            method text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_a, source_b, fid_a, fid_b)
        )
        """
    )
    op.execute("CREATE INDEX ix_feature_match_source ON feature_match (source_a)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feature_match")
