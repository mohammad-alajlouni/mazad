"""Rebuild stored booklet page plans for version 9: table values as lines.

Summary and rentals cells now carry the lines they print (a value wider than
its cell, such as a long deed number, is split so it stays inside it), and a
summary page holds at most twenty properties. Stored drafts recompose from
their own data. Approved outputs stay as approved.
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
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
