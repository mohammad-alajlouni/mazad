import os
from pathlib import Path

from sqlalchemy import select
from test_accounts import account, login
from test_agent_profile import save
from test_shared_projects import shared_project

from app.db import SessionLocal
from app.models import (
    GeneratedFile,
    GeneratedOutput,
    Project,
    ProjectImage,
    ProjectItem,
    RentalContract,
    SellingAgent,
    User,
)

CHILDREN = (
    GeneratedFile,
    GeneratedOutput,
    ProjectImage,
    ProjectItem,
    RentalContract,
    SellingAgent,
    Project,
)


def stored():
    return {path.name for path in Path(os.environ["STORAGE_DIR"]).iterdir()}


def generated(c, p):
    r = c.post(
        f"/api/projects/{p}/generate",
        json={"types": ["project_booklet", "banners", "social_content"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_deleting_a_project_removes_everything_made_from_it(admin):
    before = stored()
    p, _ = shared_project(admin)
    # The account's logo becomes the logo of each of its projects.
    assert save(admin).status_code == 200
    outputs = generated(admin, p)
    with SessionLocal() as db:
        logo = db.scalar(select(User)).agent_profile["logo_key"]
        assert db.scalars(select(ProjectImage).where(ProjectImage.key == logo)).all()
    assert len(stored() - before) > 4

    r = admin.delete(f"/api/projects/{p}")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": p}
    with SessionLocal() as db:
        for model in CHILDREN:
            assert db.scalars(select(model)).all() == [], model.__name__
    assert admin.get(f"/api/projects/{p}").status_code == 404
    assert admin.get("/api/projects").json() == []
    assert admin.get("/api/outputs").json() == []
    assert admin.get(f"/api/outputs/{outputs[0]['id']}").status_code == 404
    assert admin.delete(f"/api/projects/{p}").status_code == 404
    # Its files are gone; the account's own logo, still in use, is not.
    assert stored() - before == {logo}
    assert admin.get("/api/account/profile/logo").status_code == 200
    activity = admin.get("/api/dashboard").json()["activity"]
    assert activity[0]["action"] == "Project deleted"


def test_deleting_an_output_keeps_the_project_and_its_other_outputs(admin):
    p, item = shared_project(admin)
    outputs = generated(admin, p)
    gone = next(o for o in outputs if o["output_type"] == "banners")
    assert admin.post(f"/api/outputs/{gone['id']}/approve").status_code == 200
    gone = admin.get(f"/api/outputs/{gone['id']}").json()
    with SessionLocal() as db:
        keys = set(
            db.scalars(
                select(GeneratedFile.key).where(GeneratedFile.output_id == gone["id"])
            )
        )
    assert keys and keys <= stored()

    r = admin.delete(f"/api/outputs/{gone['id']}")
    assert r.status_code == 200, r.text
    assert admin.get(f"/api/outputs/{gone['id']}").status_code == 404
    assert admin.get(f"/api/files/{gone['files'][0]['id']}").status_code == 404
    assert not keys & stored()
    left = admin.get("/api/outputs").json()
    assert {o["output_type"] for o in left} == {"project_booklet", "social_content"}
    for o in left:
        assert admin.get(f"/api/files/{o['files'][0]['id']}").status_code == 200
    detail = admin.get(f"/api/projects/{p}").json()
    assert [i["id"] for i in detail["items"]] == [item]
    assert len(detail["images"]) == 4
    assert len(detail["outputs"]) == 2
    # The deleted output can simply be generated again.
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["banners"]})
    assert r.status_code == 200, r.text


def test_only_the_owner_deletes(admin):
    p, _ = shared_project(admin)
    output = generated(admin, p)[0]
    account(admin, "other@example.com")
    with login("other@example.com") as other:
        assert other.delete(f"/api/projects/{p}").status_code == 404
        assert other.delete(f"/api/outputs/{output['id']}").status_code == 404
    assert admin.get(f"/api/projects/{p}").status_code == 200
    assert len(admin.get("/api/outputs").json()) == 3
