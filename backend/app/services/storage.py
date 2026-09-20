from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import settings


class FileStorage(Protocol):
    def put(self, data: bytes, suffix: str) -> str: ...
    def read(self, key: str) -> bytes: ...


class LocalStorage:
    def __init__(self):
        self.root = Path(settings().storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise HTTPException(400, "Invalid file key")
        return path

    def put(self, data, suffix):
        key = f"{uuid4().hex}.{suffix}"
        self.path(key).write_bytes(data)
        return key

    def read(self, key):
        return self.path(key).read_bytes()

    def image(self, data):
        if len(data) > settings().max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "Image exceeds upload limit")
        try:
            with Image.open(BytesIO(data)) as im:
                if (
                    im.format not in ("JPEG", "PNG", "WEBP")
                    or im.width * im.height > 25000000
                ):
                    raise ValueError()
                im = ImageOps.exif_transpose(im)
                transparent = "A" in im.getbands() or "transparency" in im.info
                im = im.convert("RGBA" if transparent else "RGB")
                im.thumbnail((1600, 1600))
                out = BytesIO()
                im.save(
                    out,
                    "PNG" if transparent else "JPEG",
                    **({} if transparent else {"quality": 88}),
                )
                return self.put(out.getvalue(), "png" if transparent else "jpg")
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
        ):
            raise HTTPException(
                400, "Use a valid JPEG, PNG or WebP image, up to 25 megapixels"
            )
