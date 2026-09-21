"""Original Infath identity assets extracted from the supplied PowerPoint.

Hashes protect against accidental edits; they do not certify a finished layout.
"""

import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates/infath/assets/identity"


def load_identity():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    files = (
        manifest["icons"]
        + list(manifest["fonts"].values())
        + list(manifest["logos"].values())
    )
    # Verify at each render, including preview, so a changed/missing asset cannot
    # silently fall back to a system font or a replacement illustration.
    assets = {}
    for entry in files:
        data = (ROOT / entry["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Identity asset checksum mismatch: " + entry["file"])
        mime = "font/ttf" if entry["file"].endswith(".ttf") else "image/svg+xml"
        assets[entry["file"]] = f"data:{mime};base64," + base64.b64encode(data).decode()
    return manifest, assets.__getitem__
