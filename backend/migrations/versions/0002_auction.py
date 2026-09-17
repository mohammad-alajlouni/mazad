"""Structured auctions, relational rentals/agents, ordered images and ownership."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade():
    with op.batch_alter_table("projects") as b:
        b.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        b.create_foreign_key("fk_projects_owner", "users", ["owner_id"], ["id"])
        b.create_index("ix_projects_owner_id", ["owner_id"])
        b.add_column(sa.Column("auction", JSON, nullable=False, server_default="{}"))
    # Legacy installation is single-admin; preserve its ownership deterministically.
    op.execute(
        "UPDATE projects SET owner_id = (SELECT id FROM users ORDER BY created_at, id LIMIT 1)"
    )
    with op.batch_alter_table("audit_logs") as b:
        b.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        b.create_foreign_key("fk_audit_owner", "users", ["owner_id"], ["id"])
    op.execute(
        "UPDATE audit_logs SET owner_id = (SELECT id FROM users ORDER BY created_at, id LIMIT 1)"
    )
    with op.batch_alter_table("project_items") as b:
        b.add_column(
            sa.Column(
                "sequence_number", sa.Integer(), nullable=False, server_default="0"
            )
        )
        b.add_column(
            sa.Column("property_data", JSON, nullable=False, server_default="{}")
        )
    with op.batch_alter_table("project_images") as b:
        for name, kind, default in [
            ("category", sa.String(30), "additional"),
            ("sequence_number", sa.Integer(), "0"),
            ("caption", sa.String(300), ""),
            ("orientation", sa.String(20), "landscape"),
        ]:
            b.add_column(sa.Column(name, kind, nullable=False, server_default=default))
    for table, parent, column in [
        ("selling_agents", "projects", "project_id"),
        ("rental_contracts", "project_items", "item_id"),
    ]:
        columns = [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                column, sa.String(36), sa.ForeignKey(parent + ".id"), nullable=False
            ),
            sa.Column("data", JSON, nullable=False),
        ]
        if table == "rental_contracts":
            columns.append(
                sa.Column(
                    "sequence_number", sa.Integer(), nullable=False, server_default="0"
                )
            )
        else:
            columns.append(sa.UniqueConstraint(column))
        op.create_table(table, *columns)
        if table == "rental_contracts":
            op.create_index("ix_rental_contracts_item_id", table, ["item_id"])


def downgrade():
    op.drop_table("rental_contracts")
    op.drop_table("selling_agents")
    with op.batch_alter_table("project_images") as b:
        for name in ["category", "sequence_number", "caption", "orientation"]:
            b.drop_column(name)
    with op.batch_alter_table("project_items") as b:
        b.drop_column("sequence_number")
        b.drop_column("property_data")
    with op.batch_alter_table("audit_logs") as b:
        b.drop_constraint("fk_audit_owner", type_="foreignkey")
        b.drop_column("owner_id")
    with op.batch_alter_table("projects") as b:
        b.drop_index("ix_projects_owner_id")
        b.drop_constraint("fk_projects_owner", type_="foreignkey")
        b.drop_column("owner_id")
        b.drop_column("auction")
