"""Separate system administrators from booklet authors without changing ownership."""
from alembic import op
import sqlalchemy as sa
import os

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(20), nullable=False, server_default="user"))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    users = sa.table("users", sa.column("email"), sa.column("role"))
    op.execute(users.update().where(users.c.email == os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()).values(role="admin"))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_active")
        batch.drop_column("role")
