"""Rebuild stored booklet page plans for version 10: longer texts, more deeds.

The auction page prints its announcement and court decision as measured lines
(growing to six, then set smaller), the property page fits longer boundaries
beside their labels (smaller, or on two lines), and a property may list up to
four deeds. Stored drafts recompose from their own data. Approved outputs stay
as approved.
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
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
