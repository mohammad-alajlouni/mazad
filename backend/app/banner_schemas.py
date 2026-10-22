from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class BannerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    size: Literal["10x3", "15x5", "4x2", "6x3", "10x5", "2x2"] = "4x2"
    property_ids: list[str] = Field(default_factory=list, max_length=100)
    # The court supervising with Infath: the guide's board line reads
    # «بإشراف مركز الإسناد والتصفية - إنفاذ، و ...».
    court_name: str = Field(default="", max_length=60)
