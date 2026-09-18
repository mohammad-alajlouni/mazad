"""Native vector photo window matching the guide's diagonal corners."""

import base64
from io import BytesIO
from PIL import Image
from xml.sax.saxutils import quoteattr


def photo_frame(src, width, height):
    width, height = int(width), int(height)
    with Image.open(BytesIO(base64.b64decode(src.split(",", 1)[1]))) as image:
        ratio = min(width / image.width, height / image.height)
        w, h = image.width * ratio, image.height * ratio
    x, y = (width - w) / 2, (height - h) / 2
    cut = round(min(w, h) * 0.08)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    <defs><clipPath id="photo"><path d="M {x + cut} {y} H {x + w} V {y + h - cut} L {x + w - cut} {y + h} H {x} V {y + cut} Z"/></clipPath></defs>
    <g clip-path="url(#photo)"><image href={quoteattr(src)} width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet"/></g>
    </svg>'''
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
