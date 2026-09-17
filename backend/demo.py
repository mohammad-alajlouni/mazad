"""Exercise the real HTTP API; seed an inspectable demo and export all eight outputs."""

import argparse
import json
import os
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--code", default="DEMO-001")
    args = parser.parse_args()
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    out = ROOT / "output/demo"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.base_url + "/api", timeout=300) as client:

        def call(method, path, **kwargs):
            r = client.request(method, path, **kwargs)
            r.raise_for_status()
            return r.json()

        call(
            "POST",
            "/auth/login",
            json={"email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]},
        )
        existing = next(
            (p for p in call("GET", "/projects") if p["code"] == args.code), None
        )
        if existing:
            print(
                f"Demo project already exists: {existing['id']}. Use --code to create another demo."
            )
            return
        project = call(
            "POST",
            "/projects",
            json={
                "name": "مشروع تطوير الأصول",
                "code": args.code,
                "customer": "Demo development company",
                "description": "مشروع تجريبي لدراسة المعدات وإعداد المخرجات",
                "date": "2026-09-12",
                "location": "Amman",
                "notes": "Demo only. Equipment photograph: Jean-Daniel Drapeau-Mc Nicoll / Soerfm, CC BY-SA 3.0, Wikimedia Commons. See samples/README.md.",
            },
        )
        pid = project["id"]
        item = call(
            "POST",
            f"/projects/{pid}/items",
            json={
                "title": "وحدة طاقة صناعية",
                "reference": "PWR-001",
                "category": "Energy",
                "description": "وحدة طاقة للاستخدام الصناعي. بيانات تجريبية فقط.",
                "specifications": "Demo specification: 50 kW",
                "quantity": 1,
                "financial_value": "12500.00",
                "technical_information": "Requires client technical review",
                "notes": "Illustration photo: Jean-Daniel Drapeau-Mc Nicoll / Soerfm, CC BY-SA 3.0. https://commons.wikimedia.org/wiki/File:Montreal_power_backup.jpg",
                "attributes": {"condition": "Demo condition"},
            },
        )
        with (ROOT / "samples/demo-assets.xlsx").open("rb") as file:
            preview = call(
                "POST",
                f"/projects/{pid}/imports/preview",
                files={"file": ("demo-assets.xlsx", file)},
            )
        assert preview["valid_count"] == 3
        call("POST", f"/projects/{pid}/imports/{preview['id']}/commit")
        with (ROOT / "samples/demo-generator.jpg").open("rb") as file:
            call(
                "POST",
                f"/projects/{pid}/images",
                files={"file": ("demo-generator.jpg", file)},
                data={"item_id": item["id"]},
            )
        cfg = call("GET", "/settings")["branding"]
        cfg["default_language"] = "ar"
        call("PUT", "/settings", json=cfg)
        outputs = call("POST", f"/projects/{pid}/generate", json={"use_ai": True})
        manifest = []
        for output in outputs:
            assert output["status"] == "DRAFT"
            for file in output["files"]:
                preview = client.get("/files/" + file["id"])
                preview.raise_for_status()
            approved = call("POST", f"/outputs/{output['id']}/approve")
            assert approved["status"] == "APPROVED"
            for index, file in enumerate(approved["files"]):
                response = client.get(
                    "/files/" + file["id"], params={"download": "true"}
                )
                response.raise_for_status()
                ext = (
                    "pdf"
                    if file["media_type"] == "application/pdf"
                    else "png"
                    if file["media_type"] == "image/png"
                    else "txt"
                )
                path = out / f"{output['output_type']}-{index}.{ext}"
                path.write_bytes(response.content)
                manifest.append(
                    {
                        "output": output["output_type"],
                        "file": str(path.relative_to(ROOT)),
                        "bytes": len(response.content),
                    }
                )
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        call("POST", "/auth/logout")
        print(
            f"Validated 8 outputs; exported {len(manifest)} files. Project: {pid}. Files: {out}"
        )


if __name__ == "__main__":
    main()
