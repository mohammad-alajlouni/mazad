"""Store the selling-agent identity on the account, without modifying old outputs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "agent_profile",
            sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade():
    op.drop_column("users", "agent_profile")
