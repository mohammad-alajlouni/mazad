from pathlib import Path
import pytest
import pymupdf
from app.auction_schemas import AuctionData
from app.db import SessionLocal
from app.models import GeneratedOutput, Project
from test_banners import campaign
from test_workflow import image_data
from test_auctions import pdf


@pytest.mark.parametrize("kind", ["physical", "electronic", "hybrid"])
def test_type_fields_readiness_and_all_publications(admin, kind):
    p, item = campaign(admin, kind, workspace="project")
    for category in ["cover", "main"]:
        assert (
            admin.post(
                f"/api/projects/{p}/images",
                files={"file": ("photo.png", image_data())},
                data={
                    "category": category,
                    **({"item_id": item} if category == "main" else {}),
                },
            ).status_code
            == 200
        )
    assert (
        admin.put(
            f"/api/projects/{p}/social-config", json={"headline": "Auction opportunity"}
        ).status_code
        == 200
    )
    # Simulate a legacy record containing inactive fields. Render must ignore them.
    with SessionLocal() as db:
        project = db.get(Project, p)
        project.auction = {
            **project.auction,
            "electronic_platform_name": "PLATFORM_TEST",
            "electronic_platform_url": "https://example.com/platform-test",
            "physical_location": "VENUE_TEST",
            "auction_location_url": "https://example.com/venue-test",
            "auction_date": "2026-09-01",
            "auction_start_date": "2026-10-10",
            "auction_end_date": "2026-10-12",
        }
        db.commit()
    detail = admin.get(f"/api/projects/{p}").json()
    for rule in detail["workflow"]["rules"]["auction"].values():
        assert set(rule["required"]) <= set(rule["visible"])
    rule = detail["workflow"]["rules"]["auction"][kind]
    assert ("physical_location" in rule["required"]) == (kind != "electronic")
    assert ("auction_end_date" in rule["required"]) == (kind != "physical")
    assert all(s["valid"] for s in detail["workflow"]["stages"].values())
    r = admin.post(
        f"/api/projects/{p}/generate",
        json={
            "types": ["project_booklet", "banners", "social_content"],
            "output_language": "en",
        },
    )
    assert r.status_code == 200, r.text
    for output in r.json():
        with pymupdf.open(stream=pdf(admin, output), filetype="pdf") as doc:
            text = " ".join(page.get_text() for page in doc)
            out = Path(__file__).resolve().parents[2] / "output/auction-types"
            out.mkdir(parents=True, exist_ok=True)
            page = doc[3] if output["output_type"] == "project_booklet" else doc[0]
            page.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(
                out / f"{kind}-{output['output_type']}.png"
            )
            assert ("PLATFORM_TEST" in text) == (kind != "physical")
            assert ("VENUE_TEST" in text) == (kind != "electronic")
        with SessionLocal() as db:
            a = db.get(GeneratedOutput, output["id"]).content["project"]["auction"]
            assert bool(a["electronic_platform_url"]) == (kind != "physical")
            assert bool(a["physical_location"]) == (kind != "electronic")
            assert bool(a["auction_date"]) == (kind == "physical")
    # Required dates/venue must be detected by the saved-step check before generation.
    missing = "physical_location" if kind == "physical" else "end_time"
    with SessionLocal() as db:
        project = db.get(Project, p)
        project.auction = {
            **project.auction,
            missing: None if missing == "end_time" else "",
        }
        db.commit()
    stages = admin.get(f"/api/projects/{p}").json()["workflow"]["stages"]
    assert not stages["auction"]["valid"]
    assert any(i["field"] == missing for i in stages["auction"]["missing"])


def test_switching_type_clears_inactive_fields_before_schedule_validation():
    a = AuctionData(
        auction_type="physical",
        auction_date="2026-10-10",
        start_time="16:00",
        auction_start_date="2026-10-12",
        auction_end_date="2026-10-10",
        electronic_platform_name="OLD",
    )
    assert a.auction_end_date is None and a.electronic_platform_name == ""
    a = AuctionData(
        auction_type="electronic",
        physical_location="OLD",
        auction_location_url="https://example.com",
        auction_date="2026-09-01",
    )
    assert (
        a.physical_location == ""
        and a.auction_location_url == ""
        and a.auction_date is None
    )
