"""The Real Estate General Authority's reports, after the auction: the
auction closing form and the outputs report.

- projects.reports keeps what the author enters for them (ReportsData); the
  rest comes from the project's data.
- Their output templates are registered, as bootstrap does for new databases.
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019"
down_revision = "0018"
branch_labels = depends_on = None

KINDS = ("auction_closing", "outputs_report")


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column("reports", json_type, nullable=False, server_default="{}")
        )
    templates = sa.table(
        "templates",
        sa.column("id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("output_type", sa.String),
        sa.column("config", json_type),
    )
    bind = op.get_bind()
    known = set(bind.execute(sa.select(templates.c.output_type)).scalars())
    for kind in KINDS:
        if kind not in known:
            bind.execute(
                templates.insert().values(
                    id=str(uuid.uuid4()),
                    created_at=datetime.now(UTC),
                    output_type=kind,
                    config={"file": kind + ".html", "version": 1},
                )
            )


def downgrade():
    templates = sa.table("templates", sa.column("output_type", sa.String))
    outputs = sa.table("generated_outputs", sa.column("output_type", sa.String))
    bind = op.get_bind()
    if not bind.execute(
        sa.select(outputs.c.output_type).where(outputs.c.output_type.in_(KINDS))
    ).first():
        bind.execute(templates.delete().where(templates.c.output_type.in_(KINDS)))
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("reports")
