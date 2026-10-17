"""Rebuild stored booklet page plans for version 12.

- The introduction page (guide p.11) is set from the supervising body's
  details (Infath's, as an administrator keeps them, or another body's), and
  the agent's page in the same format; an older snapshot shows Infath's.
- The summary table's columns follow its values.
- The property description fills its region (set smaller when longer).
- The property facts wrap long plan and plot numbers, and list the deeds (up
  to eight) under one label.
- Electronic auctions print each property's scheduled closing time.
- The boundaries take the room they have beside the facts (more lines, set
  smaller when needed); only boundaries that do not fit, or deeds with
  boundaries of their own (one box per deed), go to their own page, and the
  property's page then leaves them out entirely.
- The additional-information box keeps an equal margin in both editions and
  lists nearby landmarks with their icons; the features always have their
  own page.
- A property's optional pages follow the order its author chose.
- The terms of entry are set as text (the guide's, or the auction's own).

Stored drafts recompose from their own data. Approved outputs stay as
approved.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
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
