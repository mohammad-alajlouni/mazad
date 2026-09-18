from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SocialConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    format: Literal["instagram", "x", "story"] = "instagram"
    post_kind: Literal["announcement", "property"] = "announcement"
    theme: Literal["white", "teal", "navy"] = "white"
    headline: str = Field(default="", max_length=48)
    tagline: str = Field(default="", max_length=70)
    caption: str = Field(default="", max_length=1500)
    property_ids: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def reference_combinations(self):
        if self.format != "story" and self.theme == "navy":
            raise ValueError("Navy is only available for the story reference")
        if self.format == "story" and self.post_kind != "announcement":
            raise ValueError("Story reference supports auction announcements")
        return self
