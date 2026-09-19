from sqlalchemy import select
from test_banners import campaign
from test_workflow import image_data
from app.db import SessionLocal
from app.models import GeneratedOutput, Project, ProjectItem, ProjectImage


def shared_project(c):
    p, item = campaign(c, workspace="project")
    for category, extra in [("cover", {}), ("main", {"item_id": item})]:
        r = c.post(
            f"/api/projects/{p}/images",
            files={"file": ("image.png", image_data())},
            data={"category": category, **extra},
        )
        assert r.status_code == 200
    r = c.put(
        f"/api/projects/{p}/social-config",
        json={
            "format": "instagram",
            "headline": "فرص عقارية مميزة",
            "post_kind": "property",
        },
    )
    assert r.status_code == 200
    return p, item


def test_one_project_produces_three_outputs_and_shared_edits_invalidate_all(admin):
    p, item = shared_project(admin)
    r = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": ["project_booklet", "banners", "social_content"]},
    )
    assert r.status_code == 200, r.text
    outputs = r.json()
    assert len(outputs) == 3
    assert {o["project_id"] for o in outputs} == {p}
    assert {o["preflight"]["kind"] for o in outputs} == {"booklet", "banner", "social"}
    with SessionLocal() as db:
        assert len(db.scalars(select(Project)).all()) == 1
        assert len(db.scalars(select(ProjectItem)).all()) == 1
        assert len(db.scalars(select(ProjectImage)).all()) == 4
        for o in outputs:
            content = db.get(GeneratedOutput, o["id"]).content
            assert content["items"][0]["id"] == item
            assert content["project"]["auction"]["auction_name"] == "مزاد آفاق"
            assert content["items"][0]["image_assets"]
    for o in outputs:
        r = admin.post(f"/api/outputs/{o['id']}/approve")
        assert r.status_code == 200, r.text
    # Edit the source property once: every publication must be regenerated.
    detail = admin.get(f"/api/projects/{p}").json()
    body = detail["items"][0]
    body["property_data"]["district"] = "الملقا"
    from test_auctions import property_input

    updated = property_input()
    updated["property_data"] = body["property_data"]
    assert admin.put(f"/api/projects/{p}/items/{item}", json=updated).status_code == 200
    for o in outputs:
        assert admin.post(f"/api/outputs/{o['id']}/approve").status_code == 409
        r = admin.post(f"/api/outputs/{o['id']}/regenerate")
        assert r.status_code == 200, r.text
        assert r.json()["id"] != o["id"]
        with SessionLocal() as db:
            assert (
                db.get(GeneratedOutput, r.json()["id"]).content["items"][0][
                    "property_data"
                ]["district"]
                == "الملقا"
            )
    assert admin.get("/api/dashboard").json()["total_projects"] == 1


def test_design_changes_only_invalidate_the_affected_publication(admin):
    p, _ = shared_project(admin)
    r = admin.post(
        f"/api/projects/{p}/generate",
        json={"types": ["project_booklet", "banners", "social_content"]},
    )
    assert r.status_code == 200, r.text
    outputs = {o["output_type"]: o for o in r.json()}
    for o in outputs.values():
        assert admin.post(f"/api/outputs/{o['id']}/approve").status_code == 200
    assert (
        admin.put(f"/api/projects/{p}/banner-config", json={"size": "10x3"}).status_code
        == 200
    )
    assert (
        admin.post(f"/api/outputs/{outputs['banners']['id']}/approve").status_code
        == 409
    )
    for kind in ("project_booklet", "social_content"):
        assert (
            admin.post(f"/api/outputs/{outputs[kind]['id']}/approve").status_code == 200
        )
    assert (
        admin.put(
            f"/api/projects/{p}/social-config", json={"headline": "عنوان جديد"}
        ).status_code
        == 200
    )
    assert (
        admin.post(
            f"/api/outputs/{outputs['social_content']['id']}/approve"
        ).status_code
        == 409
    )
    # A later unrelated edit must never revive an already stale banner.
    assert (
        admin.post(f"/api/outputs/{outputs['banners']['id']}/approve").status_code
        == 409
    )
    assert (
        admin.post(
            f"/api/outputs/{outputs['project_booklet']['id']}/approve"
        ).status_code
        == 200
    )


def test_default_project_and_required_data_checks(admin):
    r = admin.post("/api/projects", json={"name": "مشروع موحد", "code": "SHARED"})
    assert r.status_code == 201 and r.json()["workspace_type"] == "project"
    p = r.json()["id"]
    assert (
        admin.put(f"/api/projects/{p}/banner-config", json={"size": "4x2"}).status_code
        == 200
    )
    assert (
        admin.put(
            f"/api/projects/{p}/social-config", json={"headline": "فرصة"}
        ).status_code
        == 200
    )
    assert not admin.get(f"/api/projects/{p}/banner-review").json()["valid"]
    assert not admin.get(f"/api/projects/{p}/social-review").json()["valid"]


def test_shared_project_cannot_fall_back_to_unvalidated_legacy_booklet(admin):
    p = admin.post(
        "/api/projects", json={"name": "New project", "code": "INCOMPLETE"}
    ).json()["id"]
    assert (
        admin.post(
            f"/api/projects/{p}/items", json={"title": "Incomplete property"}
        ).status_code
        == 201
    )
    r = admin.post(f"/api/projects/{p}/generate", json={"types": ["project_booklet"]})
    assert r.status_code == 422
    assert admin.get(f"/api/projects/{p}").json()["outputs"] == []
