"""Independent social campaigns; existing project kinds are preserved."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column("social_config", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("social_config")
