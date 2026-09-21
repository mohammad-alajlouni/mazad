import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
import pymupdf
from weasyprint import HTML
from app.generation import identity
from app.generation.engine import env

SOURCE = Path(__file__).resolve().parents[1] / "design_sources/infath-identity.pptx"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def test_native_icon_geometry_and_source_provenance():
    manifest, asset = identity.load_identity()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == manifest["sha256"]
    with ZipFile(SOURCE) as archive:
        slide = ET.fromstring(archive.read("ppt/slides/slide5.xml"))
    source_paths = slide.findall(".//a:custGeom/a:pathLst/a:path", NS)
    paths = []
    assert len(manifest["icons"]) == 252
    for entry in manifest["icons"]:
        svg = ET.parse(identity.ROOT / entry["file"])
        assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
        paths.extend(svg.findall(".//{http://www.w3.org/2000/svg}path"))
    assert len(paths) == len(source_paths)
    # Every coordinate of every original custom path, not only selected samples.
    commands = {"moveTo": "M", "lnTo": "L", "cubicBezTo": "C", "close": "Z"}
    for original, svg in zip(source_paths, paths):
        expected = " ".join(
            commands[c.tag.split("}")[-1]]
            + " ".join(p.get("x") + " " + p.get("y") for p in c)
            for c in original
        )
        assert svg.get("d") == expected
    assert manifest["selected"] == {
        "time": "icon-7182.svg",
        "calendar": "icon-7745.svg",
        "location": "icon-7137.svg",
        "platform": "icon-8789.svg",
        "phone": "icon-10594.svg",
    }


def test_palette_matches_actual_powerpoint_fills():
    manifest, _ = identity.load_identity()
    with ZipFile(SOURCE) as archive:
        slide = ET.fromstring(archive.read("ppt/slides/slide2.xml"))
    fills = {
        "#" + c.get("val").upper()
        for c in slide.findall(".//p:spPr/a:solidFill/a:srgbClr", NS)
    }
    assert set(manifest["palette"].values()) - {"#FFFFFF"} <= fills


def test_tampered_asset_fails_before_render(monkeypatch, tmp_path):
    manifest = json.loads((identity.ROOT / "manifest.json").read_text())
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / manifest["icons"][0]["file"]).write_text("<svg/>")
    monkeypatch.setattr(identity, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="checksum mismatch"):
        identity.load_identity()


def test_original_font_faces_are_embedded_without_system_substitution():
    manifest, asset = identity.load_identity()
    css = env.get_template("infath/identity.css").render(
        identity=manifest, identity_asset=asset
    )
    html = "<style>" + css + "</style>"
    for family, text in [("Ruaq", "المزاد العقاري"), ("Lama", "Auction 123")]:
        for weight in [400, 500, 700]:
            html += f'<p style="font-family:{family};font-weight:{weight}">{text}</p>'
    with pymupdf.open(stream=HTML(string=html).write_pdf(), filetype="pdf") as pdf:
        names = {f[3].split("+")[-1] for f in pdf[0].get_fonts()}
        assert len(names) == 6, names
        assert all(n.startswith(("Lama", "Ruaq")) for n in names), names
        assert "Auction 123" in pdf[0].get_text()


def test_asset_failure_returns_service_error_before_template_render(monkeypatch):
    from fastapi import HTTPException
    from app.generation.engine import render_html

    def broken_assets():
        raise FileNotFoundError("missing original font")

    monkeypatch.setattr(identity, "load_identity", broken_assets)
    with pytest.raises(HTTPException) as error:
        render_html({"output_language": "ar"})
    assert error.value.status_code == 503
    assert "Official design assets" in error.value.detail
