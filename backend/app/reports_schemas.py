"""What the author enters for the Real Estate General Authority's reports,
after the auction: the auction closing form and the outputs report.

The auction's own data (its name, dates, properties, the selling agent) is
taken from the project as it is; only what happened at and around the auction
is entered here. Each property's result (sold or not, to whom, for how much)
is entered once and fills both reports.
"""

import datetime as dt
from typing import Literal

from pydantic import Field, model_validator

from .auction_schemas import Structured as Base


class Structured(Base):
    """Empty dates and counts, as a form sends them, are no value."""

    @model_validator(mode="before")
    @classmethod
    def empty_values(cls, data):
        if not isinstance(data, dict):
            return data
        optional = {
            name for name, field in cls.model_fields.items() if field.default is None
        }
        return {k: None if k in optional and v == "" else v for k, v in data.items()}


Short = Field(default="", max_length=100)
Count = Field(default=None, ge=0, le=10_000_000)


class PropertyResult(Structured):
    """One property at the auction: the closing form's row, the report's."""

    status: Literal["", "sold", "unsold"] = ""
    reason: str = Field(default="", max_length=200)  # not sold: why
    winner: str = Field(default="", max_length=150)  # sold: to whom
    value: str = Field(default="", max_length=50)  # sold: for how much
    opening_price: str = Field(default="", max_length=50)  # the report's


class ClosingForm(Structured):
    date: dt.date | None = None
    approval_number: str = Field(default="", max_length=50)


class Channel(Structured):
    content: str = Field(default="", max_length=40)
    views: str = Field(default="", max_length=30)


CHANNELS = ("x", "tiktok", "whatsapp", "sms")


class OutputsReport(Structured):
    # The cover: the period (the auction's days unless set) and the court.
    period_from: dt.date | None = None
    period_to: dt.date | None = None
    court: str = Short
    # Empty: the template's own introduction, with this auction's names.
    intro: str = Field(default="", max_length=3000)
    # Advertising boards: one location per board, one installation and one
    # removal date for all (as the template's table has them).
    boards: list[str] = Field(default_factory=list, max_length=60)
    boards_installed: dt.date | None = None
    boards_removed: dt.date | None = None
    channels: dict[Literal["x", "tiktok", "whatsapp", "sms"], Channel] = Field(
        default_factory=dict
    )
    x_posts: int | None = Count
    x_paid: int | None = Count
    x_unpaid: int | None = Count
    tiktok_videos: int | None = Count
    participants: int | None = Count
    interested: int | None = Count
    visitors: int | None = Count
    unsold_reason: str = Field(default="", max_length=1500)
    # The closing page: empty takes the selling agent's own.
    address: str = Short
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=120)


class ReportsInput(Structured):
    """What the author saves (the images are uploaded on their own)."""

    closing: ClosingForm = Field(default_factory=ClosingForm)
    report: OutputsReport = Field(default_factory=OutputsReport)
    properties: dict[str, PropertyResult] = Field(default_factory=dict)


IMAGE_LIMITS = {
    "signature": 1,
    "stamp": 1,
    "board": 30,
    "x": 3,
    "tiktok": 2,
    "whatsapp": 2,
    "youtube": 1,
}
ImageCategory = Literal[
    "signature", "stamp", "board", "x", "tiktok", "whatsapp", "youtube"
]


class ReportImage(Structured):
    id: str = Field(max_length=40)
    key: str = Field(max_length=100)
    category: ImageCategory


class ReportsData(ReportsInput):
    images: list[ReportImage] = Field(default_factory=list, max_length=60)
