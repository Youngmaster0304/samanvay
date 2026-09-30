"""enable postgis extension

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # Intentionally a no-op. PostGIS is a platform prerequisite, and the
    # postgis/postgis image provisions objects that depend on it (the tiger
    # sample data), so DROP EXTENSION fails with DependentObjectsStillExist.
    # Rolling back 0001 would mean tearing the platform down, not undoing a
    # schema change.
    pass
