"""Typed auction data shared by manual input, Excel and the renderer."""

from datetime import date, time
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Structured(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def empty_optional(cls, value, info):
        if value == "" and (
            info.field_name.endswith("_date")
            or info.field_name.endswith("_time")
            or info.field_name in ("area", "participation_amount", "annual_rent_value")
        ):
            return None
        return value

    @model_validator(mode="after")
    def urls(self):
        for key in self.__class__.model_fields:
            value = getattr(self, key)
            if value and (
                key.endswith("_url") or key.endswith("_link") or key == "website"
            ):
                parsed = urlsplit(value)
                if (
                    parsed.scheme not in ("https", "http")
                    or not parsed.hostname
                    or parsed.username
                    or any(c.isspace() for c in value)
                ):
                    raise ValueError(f"{key}: use a complete http(s) URL")
                if len(value) > 1000:
                    raise ValueError(f"{key}: URL exceeds 1000 characters")
        return self


class AuctionData(Structured):
    auction_name: str = Field(default="", max_length=200)
    auction_type: Literal["physical", "electronic", "hybrid"] = "physical"
    license_number: str = Field(default="", max_length=100)
    auction_contact_number: str = Field(default="", max_length=100)
    supervising_authority: str = Field(default="", max_length=300)
    legal_announcement_text: str = Field(default="", max_length=10000)
    court_decision_text: str = Field(default="", max_length=10000)
    auction_date: date | None = None
    auction_start_date: date | None = None
    auction_end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    physical_location: str = Field(default="", max_length=300)
    electronic_platform_name: str = Field(default="", max_length=200)
    electronic_platform_url: str = ""
    auction_location_url: str = ""
    booklet_url: str = ""
    contact_url: str = ""
    selected_cover_template_id: Literal[
        "infath-1", "infath-2", "infath-3", "infath-4", "infath-5", "infath-6"
    ] = "infath-2"
    document_language: Literal["ar", "en"] = "ar"
    # Print editions carry QR codes; digital editions carry tappable link buttons.
    booklet_edition: Literal["print", "digital"] = "print"

    @model_validator(mode="after")
    def schedule(self):
        # Inactive fields must not leak into another auction type's output.
        if self.auction_type == "physical":
            self.auction_start_date = self.auction_end_date = None
            self.electronic_platform_name = self.electronic_platform_url = ""
        else:
            self.auction_date = None
            if self.auction_type == "electronic":
                self.physical_location = self.auction_location_url = ""
        if (
            self.auction_start_date
            and self.auction_end_date
            and self.auction_end_date < self.auction_start_date
        ):
            raise ValueError("auction_end_date precedes auction_start_date")
        if (
            self.start_time
            and self.end_time
            and self.auction_start_date == self.auction_end_date
            and self.end_time < self.start_time
        ):
            raise ValueError("end_time precedes start_time")
        return self


class SellingAgentInput(Structured):
    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=10000)
    website: str = ""
    phone: str = Field(default="", max_length=100)
    whatsapp: str = Field(default="", max_length=100)
    contact_information: str = Field(default="", max_length=2000)
    social_accounts: str = Field(default="", max_length=2000)
    logo_image_id: str = ""


class Boundaries(Structured):
    north_description: str = Field(default="", max_length=3000)
    south_description: str = Field(default="", max_length=3000)
    east_description: str = Field(default="", max_length=3000)
    west_description: str = Field(default="", max_length=3000)
    north_length: str = Field(default="", max_length=100)
    south_length: str = Field(default="", max_length=100)
    east_length: str = Field(default="", max_length=100)
    west_length: str = Field(default="", max_length=100)


class RentalInput(Structured):
    unit_number: str = Field(default="", max_length=100)
    property_type: str = Field(default="", max_length=100)
    contract_status: str = Field(default="", max_length=100)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_duration: str = Field(default="", max_length=100)
    paid_period: str = Field(default="", max_length=100)
    next_due_date: date | None = None
    annual_rent_value: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )

    @model_validator(mode="after")
    def schedule(self):
        if (
            self.contract_start_date
            and self.contract_end_date
            and self.contract_end_date < self.contract_start_date
        ):
            raise ValueError("contract_end_date precedes contract_start_date")
        return self


class PropertyData(Structured):
    booklet_layout: Literal["auto", "landscape", "portrait"] = "auto"
    booklet_image_fit: Literal["cover", "contain"] = "cover"
    include_information_page: bool = True
    include_images_page: bool = True
    include_rentals_page: bool = True
    property_type: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    usage: str = Field(default="", max_length=100)
    area: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    deed_number: str = Field(default="", max_length=100)
    plan_number: str = Field(default="", max_length=100)
    plot_number: str = Field(default="", max_length=100)
    execution_request_number: str = Field(default="", max_length=100)
    participation_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    features: list[str] = Field(default_factory=list, max_length=200)
    additional_information: str = Field(default="", max_length=20000)
    auction_close_date: date | None = None
    auction_close_time: time | None = None
    survey_link: str = ""
    rental_information_link: str = ""
    additional_images_link: str = ""
    location_link: str = ""
    other_document_link: str = ""
    boundaries: Boundaries = Field(default_factory=Boundaries)
    rental_contracts: list[RentalInput] = Field(default_factory=list, max_length=1000)

    @field_validator("rental_contracts")
    @classmethod
    def populated_rentals(cls, value):
        # A newly added, untouched form row is not a rental contract. Keep zero rents.
        return [
            row
            for row in value
            if any(v not in (None, "") for v in row.model_dump().values())
        ]

    @field_validator("features")
    @classmethod
    def feature_lengths(cls, value):
        if any(len(v) > 2000 for v in value):
            raise ValueError("Feature exceeds 2000 characters")
        return [v.strip() for v in value if v.strip()]
