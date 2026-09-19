"""Make existing booklet projects shared auction projects without copying data."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.execute(
        "UPDATE projects SET workspace_type = 'project' WHERE workspace_type = 'booklet'"
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column(
            "workspace_type", existing_type=sa.String(20), server_default="project"
        )


def downgrade():
    op.execute(
        "UPDATE projects SET workspace_type = 'booklet' WHERE workspace_type = 'project'"
    )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column(
            "workspace_type", existing_type=sa.String(20), server_default="booklet"
        )
