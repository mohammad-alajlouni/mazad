"""Store banner and social configuration as JSONB on PostgreSQL, as the models do.

Migrations 0004 and 0005 created these columns as plain json while the models
declare JSONB (every other JSON column is JSONB). Values are converted in place;
SQLite has a single JSON storage and needs nothing.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = depends_on = None

COLUMNS = ("banner_config", "social_config")


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for column in COLUMNS:
        # The json default cannot be cast implicitly; restore it after the change.
        op.alter_column("projects", column, server_default=None)
        op.alter_column(
            "projects",
            column,
            type_=JSONB(),
            existing_type=sa.JSON(),
            existing_nullable=False,
            postgresql_using=f"{column}::jsonb",
        )
        op.alter_column("projects", column, server_default="{}")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for column in COLUMNS:
        op.alter_column("projects", column, server_default=None)
        op.alter_column(
            "projects",
            column,
            type_=sa.JSON(),
            existing_type=JSONB(),
            existing_nullable=False,
            postgresql_using=f"{column}::json",
        )
        op.alter_column("projects", column, server_default="{}")
