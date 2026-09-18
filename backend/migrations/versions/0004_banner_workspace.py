"""Separate banner campaigns from booklet workspaces."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column(
                "workspace_type",
                sa.String(20),
                nullable=False,
                server_default="booklet",
            )
        )
        batch.add_column(
            sa.Column("banner_config", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("banner_config")
        batch.drop_column("workspace_type")
