"""Remove variable cover ink without altering clipping paths / transparency groups.
Only sample text and paint confined to declared dynamic regions are removed.
"""

from io import BytesIO
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, NameObject
import pymupdf


def clean_cover(path, boxes):
    reader = PdfReader(path)
    page = reader.pages[0]
    stream = ContentStream(page.get_contents(), reader)
    matrix = pymupdf.Matrix(1, 0, 0, 1, 0, 0)
    clip = pymupdf.Rect(0, 0, 595.276, 841.89)
    regions = [
        pymupdf.Rect(x0, 841.89 - y1, x1, 841.89 - y0) for x0, y0, x1, y1 in boxes
    ]
    stack = []
    points = []
    pending_clip = False
    output = []

    def bounds():
        if not points:
            return pymupdf.Rect()
        return pymupdf.Rect(
            min(p.x for p in points),
            min(p.y for p in points),
            max(p.x for p in points),
            max(p.y for p in points),
        )

    def dynamic(rect):
        return not rect.is_empty and any(box.contains(rect) for box in regions)

    for values, op in stream.operations:
        if op in (b"Tj", b"TJ", b"'", b'"'):
            continue
        if op == b"q":
            stack.append((matrix, clip))
            matrix = pymupdf.Matrix(matrix)
            clip = pymupdf.Rect(clip)
        elif op == b"Q":
            if stack:
                matrix, clip = stack.pop()
        elif op == b"cm":
            matrix = pymupdf.Matrix(*[float(v) for v in values]) * matrix
        elif op in (b"m", b"l", b"c", b"v", b"y"):
            coords = [float(v) for v in values]
            points.extend(
                pymupdf.Point(coords[i], coords[i + 1]) * matrix
                for i in range(0, len(coords), 2)
            )
        elif op == b"re":
            x, y, w, h = [float(v) for v in values]
            points.extend(
                pymupdf.Point(a, b) * matrix
                for a, b in [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            )
        elif op in (b"W", b"W*"):
            pending_clip = True
        elif op in (b"f", b"F", b"f*", b"S", b"s", b"B", b"B*", b"b", b"b*", b"n"):
            rect = bounds()
            if pending_clip:
                clip = clip & rect
            if op != b"n" and dynamic(rect & clip):
                op = b"n"
            points = []
            pending_clip = False
        elif op in (b"sh", b"Do") and dynamic(clip):
            continue
        output.append((values, op))
    stream.operations = output
    page[NameObject("/Contents")] = stream
    writer = PdfWriter()
    writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
    return pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
