from abc import ABC, abstractmethod
from decimal import Decimal


class BaseOutputGenerator(ABC):
    key: str
    title: str

    @abstractmethod
    def build(self, project: dict, items: list[dict], outputs: list[dict]) -> dict: ...
    def base(self, project, items):
        total = sum(
            Decimal(str(i["quantity"])) * Decimal(str(i["financial_value"]))
            for i in items
        )
        return {
            "project": project,
            "items": items,
            "title": self.title,
            "total": str(total.quantize(Decimal(".01"))),
            "item_count": len(items),
            "review_text": "",
            "ai_status": "UNAVAILABLE",
        }


class AssetStudyGenerator(BaseOutputGenerator):
    key = "asset_study"
    title = "Asset study"

    def build(self, project, items, outputs):
        data = self.base(project, items)
        data["findings"] = [
            f"{i['title']}: {i['quantity']} units, unit value {i['financial_value']}"
            for i in items
        ]
        return data


class ProjectBookletGenerator(BaseOutputGenerator):
    key = "project_booklet"
    title = "Project booklet"

    def build(self, project, items, outputs):
        return self.base(project, items)


class BannerGenerator(BaseOutputGenerator):
    key = "banners"
    title = "Marketing banners"

    def build(self, project, items, outputs):
        return self.base(project, items)


class RegulatoryFormGenerator(BaseOutputGenerator):
    key = "regulatory_form"
    title = "Regulatory form"

    def build(self, project, items, outputs):
        data = self.base(project, items)
        data["notice"] = (
            "Development form only. Replace with the client-approved official form before regulatory use."
        )
        return data


class ClosingFormGenerator(BaseOutputGenerator):
    key = "closing_form"
    title = "Closing form"

    def build(self, project, items, outputs):
        data = self.base(project, items)
        data["notice"] = (
            "Completion details and signatures must be confirmed by the administrator. This generated draft does not certify completion."
        )
        return data


class SocialContentGenerator(BaseOutputGenerator):
    key = "social_content"
    title = "Social media content"

    def build(self, project, items, outputs):
        data = self.base(project, items)
        data["review_text"] = "\n\n".join(
            [
                project["name"],
                project["description"] or "Project overview",
                *[
                    f"{i['title']} ({i['reference']})\n{i['description']}\n{i['specifications']}"
                    for i in items
                ],
            ]
        )
        return data


class FinalOutputReportGenerator(BaseOutputGenerator):
    key = "final_output_report"
    title = "Final output report"

    def build(self, project, items, outputs):
        data = self.base(project, items)
        data["outputs"] = outputs
        return data


class BookletStudyReportGenerator(BaseOutputGenerator):
    key = "booklet_study_report"
    title = "Booklet study report"

    def build(self, project, items, outputs):
        data = self.base(project, items)
        data["findings"] = [
            f"{i['title']}: "
            + ", ".join(
                f"{field.replace('_', ' ')}: "
                + ("provided" if i.get(field) else "missing")
                for field in (
                    "description",
                    "specifications",
                    "technical_information",
                    "images",
                )
            )
            for i in items
        ]
        return data


GENERATORS = {
    g.key: g()
    for g in (
        AssetStudyGenerator,
        ProjectBookletGenerator,
        BannerGenerator,
        RegulatoryFormGenerator,
        ClosingFormGenerator,
        SocialContentGenerator,
        FinalOutputReportGenerator,
        BookletStudyReportGenerator,
    )
}
