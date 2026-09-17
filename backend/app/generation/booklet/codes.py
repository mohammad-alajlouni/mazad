import base64
from io import BytesIO
from urllib.parse import urlsplit

import qrcode
from barcode import Code128
from barcode.writer import SVGWriter


def png_data(data):
    return "data:image/png;base64," + base64.b64encode(data).decode()


def qr(url):
    if not url:
        return ""
    parts = urlsplit(url)
    if (
        parts.scheme not in ("https", "http")
        or not parts.hostname
        or len(url) > 1000
        or any(c.isspace() for c in url)
    ):
        raise ValueError("Invalid QR destination")
    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4
    )
    code.add_data(url)
    code.make(fit=True)
    stream = BytesIO()
    code.make_image(fill_color="black", back_color="white").save(stream, format="PNG")
    return png_data(stream.getvalue())


def barcode(value):
    # UUID is a stable ASCII machine identifier; no lossy transliteration of user data.
    out = BytesIO()
    Code128(value, writer=SVGWriter()).write(
        out,
        options={
            "write_text": False,
            "module_width": 0.4,
            "module_height": 12,
            "quiet_zone": 5,
        },
    )
    return "data:image/svg+xml;base64," + base64.b64encode(out.getvalue()).decode()
