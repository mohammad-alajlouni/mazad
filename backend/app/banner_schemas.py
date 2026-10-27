from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Size = Literal["10x3", "15x5", "4x2", "6x3", "10x5", "2x2"]


class BannerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # The size shown in the live preview; one of sizes.
    size: Size = "4x2"
    # Every size issued together, one output each (a campaign saved before
    # several could be chosen has its one size).
    sizes: list[Size] = Field(default_factory=list, max_length=6)
    property_ids: list[str] = Field(default_factory=list, max_length=100)
    # The court supervising with Infath: the guide's board line reads
    # «بإشراف مركز الإسناد والتصفية - إنفاذ، و ...».
    court_name: str = Field(default="", max_length=60)

    @model_validator(mode="after")
    def chosen_sizes(self):
        self.sizes = list(dict.fromkeys(self.sizes)) or [self.size]
        if self.size not in self.sizes:
            self.size = self.sizes[0]
        return self
