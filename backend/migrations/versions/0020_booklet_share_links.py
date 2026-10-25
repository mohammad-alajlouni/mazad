"""The booklet's public link: every project gets a share token of its own
(services/sharing.py), the address its QR codes open without signing in.
"""

import secrets

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("share_token", sa.String(24), nullable=True))
    projects = sa.table(
        "projects", sa.column("id", sa.String), sa.column("share_token", sa.String)
    )
    bind = op.get_bind()
    for (id,) in bind.execute(sa.select(projects.c.id)).all():
        bind.execute(
            projects.update()
            .where(projects.c.id == id)
            .values(share_token=secrets.token_urlsafe(9))
        )
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("share_token", existing_type=sa.String(24), nullable=False)
        batch.create_unique_constraint("uq_projects_share_token", ["share_token"])


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("uq_projects_share_token", type_="unique")
        batch.drop_column("share_token")
