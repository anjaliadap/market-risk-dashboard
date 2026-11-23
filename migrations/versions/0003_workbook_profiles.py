"""Separate workbook profiles without replacing existing saved snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("workbook_imports")}
    if "profile" not in columns:
        op.add_column(
            "workbook_imports",
            sa.Column("profile", sa.String(40), nullable=False, server_default="legacy"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("workbook_imports")}
    if "ix_workbook_imports_profile" not in indexes:
        op.create_index("ix_workbook_imports_profile", "workbook_imports", ["profile"])


def downgrade():
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("workbook_imports")}
    if "ix_workbook_imports_profile" in indexes:
        op.drop_index("ix_workbook_imports_profile", table_name="workbook_imports")
    with op.batch_alter_table("workbook_imports") as batch:
        batch.drop_column("profile")
