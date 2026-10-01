"""feature_match.pair_features

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01

Plan Stage 4 rest. Every accepted pair stores the feature values the scorer saw
(IoU, intersection over min-area, centroid distance, area ratio, orientation and
compactness differences, attribute similarity), so a reviewer can later be shown
WHY a pair was accepted instead of only its final score.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE feature_match ADD COLUMN pair_features jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE feature_match DROP COLUMN IF EXISTS pair_features")
