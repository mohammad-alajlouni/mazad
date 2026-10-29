"""Typed auction data shared by manual input, Excel and the renderer."""

import re
from datetime import date, time
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# A website's host: a real domain name (labels, then a top-level name).
DOMAIN = re.compile(
    r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})$"
)


class Structured(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def empty_optional(cls, value, info):
        if value == "" and (
            info.field_name.endswith("_date")
            or info.field_name.endswith("_time")
            or info.field_name
            in (
                "area",
                "participation_amount",
                "annual_rent_value",
                "close_interval_minutes",
            )
        ):
            return None
        return value

    @field_validator("website", mode="before", check_fields=False)
    @classmethod
    def website_scheme(cls, value):
        # A website may be typed as www.aayan.com: https:// is added here.
        text = str(value or "").strip()
        if text and not re.match(r"^[a-z][a-z0-9+.-]*://", text, re.I):
            text = "https://" + text
        return text

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
                    or (key == "website" and not DOMAIN.match(parsed.hostname))
                ):
                    raise ValueError(f"{key}: use a complete http(s) URL")
                if len(value) > 1000:
                    raise ValueError(f"{key}: URL exceeds 1000 characters")
        return self


class AuctionData(Structured):
    auction_name: str = Field(default="", max_length=200)
    # Infath's assignment number for the auction: kept with it, not printed.
    assignment_number: str = Field(default="", max_length=100)
    auction_type: Literal["physical", "electronic", "hybrid"] = "physical"
    license_number: str = Field(default="", max_length=100)
    auction_contact_number: str = Field(default="", max_length=100)
    supervising_authority: str = Field(default="", max_length=300)
    legal_announcement_text: str = Field(default="", max_length=10000)
    court_decision_text: str = Field(default="", max_length=10000)
    # The terms of entry, when this auction's differ from the guide's
    # (empty: the guide's, see generation/booklet/terms.py).
    terms_text: str = Field(default="", max_length=10000)
    auction_date: date | None = None
    auction_start_date: date | None = None
    auction_end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    # Electronic bidding closes property by property: the first at this time,
    # each next one this many minutes later, on the auction's last day. A
    # property's own closing date or time, when given, overrides its share.
    first_close_time: time | None = None
    close_interval_minutes: int | None = Field(default=None, ge=0, le=1440)
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
    # The supervising body: Infath (its logo and introduction page, as an
    # administrator keeps them), or another body giving its own.
    supervisor: Literal["infath", "other"] = "infath"
    supervisor_title: str = Field(default="", max_length=200)
    supervisor_text: str = Field(default="", max_length=3000)
    supervisor_phone: str = Field(default="", max_length=100)
    supervisor_website: str = Field(default="", max_length=200)
    supervisor_social: str = Field(default="", max_length=300)
    # Print editions carry QR codes; digital editions carry tappable link buttons.
    booklet_edition: Literal["print", "digital"] = "print"

    @field_validator("terms_text", mode="before")
    @classmethod
    def own_terms(cls, value):
        # Terms left as the guide's (for any kind of auction) are not kept:
        # they follow the guide, the auction's kind choosing its terms.
        from .generation.booklet.terms import GUIDE_TEXTS

        text = str(value or "").replace("\r\n", "\n").strip()
        return "" if text in GUIDE_TEXTS.values() else text

    @model_validator(mode="after")
    def schedule(self):
        # Inactive fields must not leak into another auction type's output.
        if self.auction_type == "physical":
            self.auction_start_date = self.auction_end_date = None
            self.first_close_time = self.close_interval_minutes = None
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


# Icons a nearby landmark may carry in the additional information (see
# booklet-art/landmarks): the guide's own icons and a few drawn alike.
LANDMARK_ICONS = (
    "road",
    "hospital",
    "school",
    "mosque",
    "market",
    "park",
    "airport",
    "station",
    "bank",
    "government",
    "location",
    "city",
)


class Landmark(Structured):
    icon: Literal[LANDMARK_ICONS] = "location"
    text: str = Field(default="", max_length=60)


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
    include_features_page: bool = True
    # The boundaries on a page of their own though they fit beside the facts.
    include_boundaries_page: bool = False
    # The optional pages in the author's order (composer.OPTIONAL_PAGES).
    page_order: list[
        Literal["features", "boundaries", "information", "images", "rentals"]
    ] = Field(default_factory=list, max_length=5)
    property_type: str = Field(default="", max_length=100)
    city: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    usage: str = Field(default="", max_length=100)
    area: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    deed_number: str = Field(default="", max_length=100)
    # A property may stand on up to eight deeds: the first above, the rest here.
    extra_deed_numbers: list[str] = Field(default_factory=list, max_length=7)
    plan_number: str = Field(default="", max_length=100)
    plot_number: str = Field(default="", max_length=100)
    execution_request_number: str = Field(default="", max_length=100)
    participation_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=2
    )
    features: list[str] = Field(default_factory=list, max_length=200)
    # Nearby landmarks, each with its icon, in the additional information.
    landmarks: list[Landmark] = Field(default_factory=list, max_length=12)
    additional_information: str = Field(default="", max_length=20000)
    auction_close_date: date | None = None
    auction_close_time: time | None = None
    survey_link: str = ""
    rental_information_link: str = ""
    additional_images_link: str = ""
    location_link: str = ""
    other_document_link: str = ""
    boundaries: Boundaries = Field(default_factory=Boundaries)
    # Deeds with boundaries and lengths of their own: each deed then has its
    # box on the boundaries page. The first deed's are those above; the
    # further deeds' follow extra_deed_numbers, in the same order.
    deeds_differ: bool = False
    deed_boundaries: list[Boundaries] = Field(default_factory=list, max_length=7)
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

    @model_validator(mode="before")
    @classmethod
    def deeds_with_their_boundaries(cls, data):
        # An empty deed row is dropped below; its boundaries go with it, so
        # each further deed keeps its own.
        if isinstance(data, dict) and isinstance(data.get("deed_boundaries"), list):
            deeds = data.get("extra_deed_numbers")
            if isinstance(deeds, list):
                data = {
                    **data,
                    "deed_boundaries": [
                        own
                        for deed, own in zip(deeds, data["deed_boundaries"])
                        if str(deed or "").strip()
                    ],
                }
        return data

    @field_validator("extra_deed_numbers", mode="before")
    @classmethod
    def entered_deeds(cls, value):
        # An added but empty deed row is not a deed.
        if not isinstance(value, list):
            return value
        kept = [str(v).strip() for v in value if str(v or "").strip()]
        if any(len(v) > 100 for v in kept):
            raise ValueError("Deed number exceeds 100 characters")
        return kept

    @field_validator("landmarks")
    @classmethod
    def landmarks_written(cls, value):
        return [v for v in value if v.text]

    @field_validator("features")
    @classmethod
    def feature_lengths(cls, value):
        if any(len(v) > 2000 for v in value):
            raise ValueError("Feature exceeds 2000 characters")
        return [v.strip() for v in value if v.strip()]
