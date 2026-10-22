"""Local immutable Excel snapshots. No sponsor data is embedded in migrations."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    # Older app startup uses create_all; tolerate that table already existing.
    if not sa.inspect(op.get_bind()).has_table("workbook_imports"):
        op.create_table(
            "workbook_imports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=True),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
        )


def downgrade():
    op.drop_table("workbook_imports")
