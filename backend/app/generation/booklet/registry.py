"""Controlled templates derived from Infath V2, pages 9–26."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TemplateDefinition:
    id: str
    name_ar: str
    name_en: str
    variant: str
    display_order: int
    document_type: str = "project_booklet"
    supported_auction_types: tuple = ("physical", "electronic", "hybrid")
    languages: tuple = ("ar", "en")
    required_fields: tuple = ("auction_name",)
    optional_fields: tuple = ("auction_logo", "agent_logo")
    renderer: str = "infath/cover.html"


COVERS = {
    f"infath-{i}": TemplateDefinition(f"infath-{i}", ar, en, variant, i)
    for i, ar, en, variant in [
        (1, "صورة كاملة", "Full photograph", "photo-full"),
        (2, "أزرق داكن", "Dark blue", "blue"),
        (3, "فيروزي", "Teal", "teal"),
        (4, "أزرق متدرج", "Blue gradient", "blue-gradient"),
        (5, "فيروزي متدرج", "Teal gradient", "teal-gradient"),
        (6, "صورة علوية", "Top photograph", "photo-top"),
    ]
}


def cover_options():
    return [
        {**asdict(c), "thumbnail": f"/api/booklet-templates/{c.id}/thumbnail"}
        for c in COVERS.values()
    ]
