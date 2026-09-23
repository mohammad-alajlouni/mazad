"""Migrations run on their own database: schema matches the models, and stored
outputs are upgraded where the code needs it (0008: booklet page plan)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa

from app.auction_schemas import AuctionData, PropertyData
from app.generation.booklet.composer import LAYOUT_VERSION, compose

BACKEND = Path(__file__).resolve().parents[1]
OUTPUTS = sa.table(
    "generated_outputs",
    sa.column("id", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
    sa.column("project_id", sa.String),
    sa.column("output_type", sa.String),
    sa.column("status", sa.String),
    sa.column("content", sa.JSON),
    sa.column("template_id", sa.String),
    sa.column("revision", sa.Integer),
)


def alembic(url, *args):
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "JWT_SECRET": "migration-test-only-secret-0000000000000000000",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        check=False,  # the return code is asserted with alembic output below
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout + result.stderr


def old_booklet_content():
    """An output as the composer wrote it before the reference rebuild."""
    project = {
        "id": str(uuid4()),
        "auction": AuctionData.model_validate(
            {"auction_name": "مزاد قديم", "auction_type": "electronic"}
        ).model_dump(mode="json"),
        "selling_agent": {"name": "وكيل"},
    }
    items = [
        {
            "id": str(uuid4()),
            "title": "عقار",
            "description": "وصف",
            "notes": "",
            "property_data": PropertyData.model_validate(
                {"property_type": "فيلا", "auction_close_date": "2026-10-12"}
            ).model_dump(mode="json"),
            "image_assets": [],
        }
    ]
    booklet = compose(json.loads(json.dumps(project)), json.loads(json.dumps(items)))
    booklet["layout_version"] = 3
    booklet["pages"] = [
        {k: v for k, v in page.items() if k not in ("variant", "edition", "info")}
        for page in booklet["pages"]
    ]
    return {"project": project, "items": items, "booklet": booklet}


def test_migrations_match_models_and_upgrade_stored_booklets(tmp_path):
    # MIGRATION_TEST_DATABASE_URL runs the same check on PostgreSQL (JSONB).
    url = os.environ.get("MIGRATION_TEST_DATABASE_URL") or (
        f"sqlite:///{tmp_path / 'migrations.db'}"
    )
    engine = sa.create_engine(url)
    if engine.dialect.name != "sqlite":
        assert url.rstrip("/").endswith("_test"), "use a disposable *_test database"
        with engine.begin() as db:
            db.execute(sa.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    alembic(url, "upgrade", "0007")
    content = old_booklet_content()
    with engine.begin() as db:
        # Foreign keys are not the subject here; PostgreSQL enforces them.
        if engine.dialect.name != "sqlite":
            db.execute(sa.text("SET session_replication_role = replica"))
        for output_id, status in (("draft", "DRAFT"), ("approved", "APPROVED")):
            db.execute(
                OUTPUTS.insert().values(
                    id=output_id,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                    project_id="p",
                    output_type="project_booklet",
                    status=status,
                    content=content,
                    template_id="t",
                    revision=1,
                )
            )
    alembic(url, "upgrade", "head")
    assert "No new upgrade operations detected" in alembic(url, "check")
    with engine.connect() as db:
        stored = {
            row.id: row.content
            for row in db.execute(sa.select(OUTPUTS.c.id, OUTPUTS.c.content))
        }
    draft = stored["draft"]["booklet"]
    assert draft["layout_version"] == LAYOUT_VERSION
    page = next(p for p in draft["pages"] if p["kind"] == "property")
    assert page["variant"] == "landscape-close" and page["edition"] == "print"
    # The data snapshot is untouched; approved records stay exactly as approved.
    assert stored["draft"]["items"] == content["items"]
    assert stored["approved"] == content


def test_draft_generated_before_the_new_page_plan_can_still_be_approved(admin):
    """Re-rendering (approve, edit) rebuilds an old plan from the stored snapshot."""
    from test_auctions import add, create_auction, generate, property_input

    from app.db import SessionLocal
    from app.models import GeneratedOutput

    p = create_auction(admin)
    add(admin, p, property_input())
    output = generate(admin, p)
    with SessionLocal() as db:
        row = db.get(GeneratedOutput, output["id"])
        booklet = {**row.content["booklet"], "layout_version": 3}
        booklet["pages"] = [
            {k: v for k, v in page.items() if k not in ("variant", "edition", "info")}
            for page in booklet["pages"]
        ]
        row.content = {**row.content, "booklet": booklet}
        db.commit()
    approved = admin.post("/api/outputs/" + output["id"] + "/approve")
    assert approved.status_code == 200, approved.text
    with SessionLocal() as db:
        stored = db.get(GeneratedOutput, output["id"]).content["booklet"]
    assert stored["layout_version"] == LAYOUT_VERSION


def test_booklet_migration_skips_drafts_it_cannot_rebuild(tmp_path):
    url = f"sqlite:///{tmp_path / 'broken.db'}"
    alembic(url, "upgrade", "0007")
    engine = sa.create_engine(url)
    broken = {"project": {"auction": {"auction_type": "?"}}, "booklet": {"pages": []}}
    with engine.begin() as db:
        db.execute(
            OUTPUTS.insert().values(
                id="broken",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
                project_id="p",
                output_type="project_booklet",
                status="DRAFT",
                content=broken,
                template_id="t",
                revision=1,
            )
        )
    alembic(url, "upgrade", "head")
    with engine.connect() as db:
        assert db.execute(sa.select(OUTPUTS.c.content)).scalar_one() == broken
