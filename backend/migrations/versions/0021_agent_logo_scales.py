"""The size of the selling agent's logo, per kind of output (the author's, from
the live preview): {"booklet": 0.8, "banner": 1.0, "social": 0.6}.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0021"
down_revision = "0020"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column(
                "agent_logo_scales",
                sa.JSON().with_variant(JSONB(), "postgresql"),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("agent_logo_scales")
