import copy
import json
from sqlalchemy import select
from app.db import SessionLocal
from app.models import GeneratedOutput, ProjectImage
from test_accounts import account, login
from test_auctions import create_auction, add, property_input, generate
from test_workflow import image_data

FIELDS = {
    "name": "وكيل الحساب",
    "description": "شركة متخصصة في بيع وتسويق العقارات",
    "phone": "0555111111",
    "website": "https://example.com",
    "whatsapp": "0555222222",
    "contact_information": "الرياض",
    "social_accounts": "@account",
}


def save(client, values=None, logo=True):
    return client.put(
        "/api/account/profile",
        data={"data": json.dumps(values or FIELDS)},
        files={"file": ("logo.png", image_data(), "image/png")} if logo else None,
    )


def test_profile_required_fields_and_private_logo(admin):
    assert not admin.get("/api/auth/me").json()["profile_complete"]
    assert admin.get("/api/account/profile").json() == {
        "values": {},
        "has_logo": False,
        "complete": False,
    }
    assert admin.get("/api/account/profile/logo").status_code == 404
    assert save(admin, logo=False).status_code == 422
    for value in (
        {**FIELDS, "name": "   "},
        {**FIELDS, "phone": ""},
        {**FIELDS, "website": "file:///etc/passwd"},
        {**FIELDS, "logo_key": "foreign.png"},
        {**FIELDS, "logo_image_id": "foreign"},
    ):
        assert save(admin, value).status_code == 422
    assert (
        admin.put(
            "/api/account/profile",
            data={"data": json.dumps(FIELDS)},
            files={"file": ("bad.png", b"not an image", "image/png")},
        ).status_code
        == 400
    )
    assert not admin.get("/api/auth/me").json()["profile_complete"]
    response = save(admin)
    assert response.status_code == 200, response.text
    assert response.json()["complete"]
    assert "logo_key" not in response.json()["values"]
    assert admin.get("/api/auth/me").json()["profile_complete"]
    assert admin.get("/api/account/profile/logo").status_code == 200
    account(admin, "profile-other@example.com")
    with login("profile-other@example.com") as other:
        assert other.get("/api/account/profile/logo").status_code == 404
        assert other.get("/api/account/profile").json()["values"] == {}


def test_profile_updates_owned_projects_and_preserves_output_snapshot(admin):
    account(admin, "profile-owner@example.com")
    account(admin, "untouched@example.com")
    with (
        login("profile-owner@example.com") as owner,
        login("untouched@example.com") as other,
    ):
        p = create_auction(owner, workspace="booklet")
        foreign = create_auction(other, cover="infath-3", workspace="booklet")
        add(owner, p, property_input())
        output = generate(owner, p)
        assert owner.post(f"/api/outputs/{output['id']}/approve").status_code == 200
        with SessionLocal() as db:
            snapshot = copy.deepcopy(db.get(GeneratedOutput, output["id"]).content)
        assert (
            owner.get("/api/account/profile").json()["values"]["name"]
            == "شركة آفاق العقارية"
        )
        assert save(owner).status_code == 200
        detail = owner.get(f"/api/projects/{p}").json()
        assert detail["selling_agent"]["name"] == FIELDS["name"]
        assert detail["outputs"][0]["status"] == "NEEDS_REGENERATION"
        assert detail["workflow"]["stages"]["agent"]["valid"]
        assert (
            other.get(f"/api/projects/{foreign}").json()["selling_agent"]["name"]
            != FIELDS["name"]
        )
        with SessionLocal() as db:
            assert db.get(GeneratedOutput, output["id"]).content == snapshot
        r = owner.post(
            "/api/projects", json={"name": "New project", "code": "PROFILE_NEW"}
        )
        assert r.status_code == 201, r.text
        new = r.json()["id"]
        detail2 = owner.get(f"/api/projects/{new}").json()
        assert detail2["selling_agent"]["phone"] == FIELDS["phone"]
        assert (
            detail2["selling_agent"]["logo_image_id"]
            != detail["selling_agent"]["logo_image_id"]
        )
        assert (
            owner.put(
                f"/api/projects/{p}/selling-agent", json={"name": "Override"}
            ).status_code
            == 409
        )
        assert (
            owner.post(
                f"/api/projects/{p}/images",
                data={"category": "agent_logo"},
                files={"file": ("logo.png", image_data())},
            ).status_code
            == 409
        )
        assert (
            save(owner, {**FIELDS, "name": "Updated account"}, logo=False).status_code
            == 200
        )
        for id in (p, new):
            assert (
                owner.get(f"/api/projects/{id}").json()["selling_agent"]["name"]
                == "Updated account"
            )
        before = owner.get(f"/api/projects/{new}").json()["project"]["revision"]
        assert (
            save(owner, {**FIELDS, "name": "Updated account"}, logo=False).status_code
            == 200
        )
        assert owner.get(f"/api/projects/{new}").json()["project"]["revision"] == before
        with SessionLocal() as db:
            keys = db.scalars(
                select(ProjectImage.key).where(ProjectImage.project_id.in_([p, new]))
            ).all()
            assert len(set(keys)) == 1
