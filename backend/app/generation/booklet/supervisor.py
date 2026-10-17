"""The body that supervises the auction: Infath, or another body.

Its logo stands where the guide puts Infath's (covers, page footers, its
introduction page) and its introduction page (guide p.11) carries its name,
text and contact details. Infath's are the guide's; an administrator can
replace them (a new logo, a changed text) without editing any design, and an
auction under another body gives that body's own.
"""

INFATH = {
    "kind": "infath",
    "title": "مركز الإسناد والتصفية - إنفاذ",
    "text": (
        "مركز الإسناد والتصفية «إنفاذ»، مركز حكومي؛ يختص بالإشراف على أعمال "
        "التصفية والبيع للأصول الثابتة والمنقولة والتي تُسند إليه من قبل الجهات "
        "القضائية والحكومية كتصفية التركات والشركات والصناديق والمساهمات، وذلك "
        "من خلال إسنادها إلى الجهات المتخصصة فنيًا والإشراف على أعمالها؛ "
        "للإسهام في تسريع عملية استيفاء الحقوق."
    ),
    "phone": "920000100",
    "website": "www.infath.gov.sa",
    "social": "infath_sa\ninfathauctions",
    "logo": "",
}
# The details an administrator may change, and an auction under another body
# gives (as supervisor_<key> in its auction data).
FIELDS = ("title", "text", "phone", "website", "social")


def supervisor_of(auction, settings=None, logo="", infath_logo=""):
    """The supervising body of an auction, ready for the booklet.

    settings: the administrator's changes to Infath's details (system settings,
    under "infath_<key>"); logo: the other body's logo, infath_logo: a logo an
    administrator gave Infath (both as data URIs; empty keeps the guide's).
    """
    auction = auction or {}
    if auction.get("supervisor") == "other":
        return {
            "kind": "other",
            **{
                key: str(auction.get(f"supervisor_{key}") or "").strip()
                for key in FIELDS
            },
            "logo": logo,
        }
    settings = settings or {}
    return {
        **INFATH,
        **{
            key: str(settings[f"infath_{key}"]).strip()
            for key in FIELDS
            if str(settings.get(f"infath_{key}") or "").strip()
        },
        "logo": infath_logo,
    }
