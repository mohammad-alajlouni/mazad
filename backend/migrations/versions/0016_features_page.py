"""Rebuild stored booklet page plans for version 11: the features page.

A property with features and more than one additional photograph gets the
guide's page 17 after its first page: its main photograph and two additional
ones, with the features as numbered points (no longer inside the first page's
additional-information box). Stored drafts recompose from their own data.
Approved outputs stay as approved.
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = depends_on = None

outputs = sa.table(
    "generated_outputs",
    sa.column("id", sa.String),
    sa.column("output_type", sa.String),
    sa.column("status", sa.String),
    sa.column("content", sa.JSON),
)


def upgrade():
    from app.generation.booklet.composer import current_booklet

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(outputs.c.id, outputs.c.content).where(
            outputs.c.output_type == "project_booklet",
            outputs.c.status != "APPROVED",
        )
    ).all()
    for output_id, content in rows:
        if not isinstance(content, dict):
            continue
        try:
            upgraded, changed = current_booklet(content)
        except Exception:  # noqa: BLE001
            # The renderer retries the same upgrade if this draft is re-rendered.
            continue
        if changed:
            bind.execute(
                outputs.update()
                .where(outputs.c.id == output_id)
                .values(content=upgraded)
            )


def downgrade():
    # The previous page plan cannot be reproduced; drafts are regenerated instead.
    pass
