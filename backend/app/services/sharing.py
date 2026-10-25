"""The booklet's public link: what an auction's QR codes open.

Every project has a share token of its own (projects.share_token). Its link,
<platform>/api/b/<token>, opens a page anyone can read without signing in,
showing the project's booklet page by page (the approved one, else the latest
issued). The booklet link the author types is used as entered when it leads
elsewhere; empty, or a link into the platform itself (its files and pages ask
for a session, so a phone scanning the code sees nothing), the public link
takes its place.
"""

import secrets
from contextvars import ContextVar
from urllib.parse import urlsplit

from ..config import settings

# The platform's address as the request reached it (set per request in
# main.py); PUBLIC_URL, when configured, wins.
REQUEST_BASE: ContextVar[str] = ContextVar("request_base", default="")


RESERVED = ("example.com", "example.org", "example.net")


def new_token():
    return secrets.token_urlsafe(9)


def request_base(host, scheme):
    """The platform's address from a request's host. A domain is served over
    HTTPS (TLS ends before nginx, which reports plain http); a local address
    keeps the scheme it came in on."""
    if not host:
        return ""
    name = host.split(",")[0].strip()
    bare = name.rsplit(":", 1)[0].strip("[]")
    local = bare == "localhost" or bare.replace(".", "").isdigit() or ":" in bare
    scheme = scheme.split(",")[0].strip() if local or bare == "testserver" else "https"
    return f"{scheme}://{name}"


def public_base():
    return (settings().public_url or REQUEST_BASE.get() or "").rstrip("/")


def booklet_link(token):
    base = public_base()
    return f"{base}/api/b/{token}" if base and token else ""


def booklet_url(entered, token):
    """The link the QR codes carry."""
    link = booklet_link(token)
    entered = (entered or "").strip()
    if not entered:
        return link
    own = urlsplit(public_base()).hostname
    target = urlsplit(entered)
    if own and target.hostname == own and not target.path.startswith("/api/b/"):
        return link
    # A placeholder (the reserved example domains, as the sample fill once
    # wrote) never leads to a booklet.
    host = target.hostname or ""
    if host in RESERVED or host.endswith(tuple("." + h for h in RESERVED)):
        return link
    return entered
