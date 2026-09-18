from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .banner_schemas import BannerConfig
from .social_schemas import SocialConfig
from .auction_schemas import AuctionData, PropertyData


class ProjectInput(BaseModel):
    workspace_type: Literal["booklet", "banners", "social"] = "booklet"
    social_config: SocialConfig = Field(default_factory=SocialConfig)
    banner_config: BannerConfig = Field(default_factory=BannerConfig)
    auction: AuctionData | None = None
    status: Literal["DRAFT", "ACTIVE", "COMPLETED"] = "DRAFT"
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=100)
    customer: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=10000)
    date: str = Field(default="", max_length=20)
    location: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=10000)

    @field_validator("name", "code")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Must not be blank")
        return v.strip()


class ItemInput(BaseModel):
    property_data: PropertyData = Field(default_factory=PropertyData)
    sequence_number: int = Field(default=0, ge=0)
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    reference: str = Field(default="", max_length=100)
    category: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=10000)
    specifications: str = Field(default="", max_length=10000)
    quantity: Decimal = Field(default=Decimal(1), gt=0, max_digits=18, decimal_places=4)
    financial_value: Decimal = Field(
        default=Decimal(0), ge=0, max_digits=18, decimal_places=2
    )
    technical_information: str = Field(default="", max_length=10000)
    notes: str = Field(default="", max_length=10000)
    attributes: dict = Field(default_factory=dict)


class Branding(BaseModel):
    organization_name: str = Field(default="كُتَيِّب", max_length=200)
    primary_color: str = Field(default="#176858", pattern=r"^#[0-9a-fA-F]{6}$")
    default_language: str = Field(default="ar", pattern="^(en|ar)$")
    logo_key: str = ""
