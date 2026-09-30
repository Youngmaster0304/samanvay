"""create source_registry

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29

Provenance for one uploaded file. The column list matches app/db/models.py; the schema
document is backend.md §4.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_registry",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("authority", sa.Text(), nullable=True),
        sa.Column("licence", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("vintage", sa.Date(), nullable=True),
        sa.Column(
            "is_synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("sigma_m", sa.Double(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("client_key", sa.Text(), nullable=True),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("crs_original", sa.Text(), nullable=True),
        sa.Column("crs_declared", sa.Text(), nullable=True),
        sa.Column("crs_used", sa.Text(), nullable=True),
        sa.Column("crs_source", sa.String(32), nullable=False),
        sa.Column("has_geometry", sa.Boolean(), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=True),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "geometry_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("layer", sa.Text(), nullable=True),
        sa.Column(
            "layers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("raster", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "notes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_source_registry_sha256_kind",
        "source_registry",
        ["sha256", "kind"],
        unique=True,
    )
    op.create_index(
        "ix_source_registry_client_key",
        "source_registry",
        ["client_key"],
        unique=True,
    )
    op.create_index("ix_source_registry_kind", "source_registry", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_source_registry_kind", table_name="source_registry")
    op.drop_index("ix_source_registry_client_key", table_name="source_registry")
    op.drop_index("uq_source_registry_sha256_kind", table_name="source_registry")
    op.drop_table("source_registry")
