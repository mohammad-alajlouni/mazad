"""Checks of texts entered outside a project that the booklet must hold."""


def text_issue(text):
    """Whether an introduction text is too long for its one page even at the
    smallest size (see composer.profile_size)."""
    from ..generation.booklet.composer import profile_size

    text = (text or "").strip()
    return bool(text) and not profile_size(text)[1]
