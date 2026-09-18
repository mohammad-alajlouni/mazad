import base64
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "templates/infath/assets"


@lru_cache(maxsize=32)
def asset(name):
    mime = (
        "image/svg+xml"
        if name.endswith(".svg")
        else "image/png"
        if name.endswith(".png")
        else "font/otf"
        if name.endswith(".otf")
        else "font/ttf"
    )
    return (
        f"data:{mime};base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()
    )
