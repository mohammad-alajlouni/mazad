"""Rebuild stored booklet page plans for the reference layout (version 4).

Generated outputs keep the data snapshot they were made from and the page
plan the composer produced. The reference rebuild changed that plan (page
variants, edition, information box entries), so drafts written before it are
recomposed here from their own snapshot; their data does not change.

Approved outputs are records with their PDF already stored: they are left
exactly as approved. The renderer applies the same upgrade to any draft this
migration did not reach, so the two paths cannot disagree.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
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
            # One unusual stored draft must not block the release; the renderer
            # retries the same upgrade if that draft is ever re-rendered.
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
