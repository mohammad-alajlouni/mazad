"""What the author enters for the auction's official forms.

Everything the booklet already holds (the auction, its properties, the
selling agent) is taken from it as it is; only what the booklet does not hold
is entered here (generation/forms/shared.py lists what comes from where).
"""

import datetime as dt
from typing import Literal

from pydantic import Field, field_validator

from .auction_schemas import Structured
from .generation.forms.questions import QUESTIONS

YesNo = Literal["", "yes", "no"]
Text = Field(default="", max_length=300)
Long = Field(default="", max_length=3000)


class StudyAnswer(Structured):
    answer: YesNo = ""
    note: str = Field(default="", max_length=2000)


class PropertyForms(Structured):
    """One property's own values: in the request form (its row of the
    statement, its agent) and its study."""

    owner: str = Text
    agent_name: str = Text
    agency_number: str = Field(default="", max_length=100)
    # Shared by both forms.
    age: str = Field(default="", max_length=50)
    status: Literal["", "free", "seized", "mortgaged", "stopped", "other"] = ""
    status_other: str = Text
    min_price: str = Field(default="", max_length=100)
    estimated_value: str = Field(default="", max_length=100)
    disclosure: str = Text
    # The study.
    location_note: str = Long
    answers: dict[str, StudyAnswer] = Field(default_factory=dict)
    estimated_price: str = Field(default="", max_length=100)
    indicative_value: str = Field(default="", max_length=100)
    defects: str = Long
    # Empty: the booklet's features of the property.
    features: str = Long

    @field_validator("answers")
    @classmethod
    def known_questions(cls, value):
        unknown = set(value) - set(QUESTIONS)
        if unknown:
            raise ValueError(f"Unknown study questions: {sorted(unknown)}")
        return value


class Disclosure(Structured):
    answer: YesNo = ""
    text: str = Text


class RequestForm(Structured):
    """The authority's auction request form: what the booklet does not hold."""

    date: dt.date | None = None
    # The establishment (its name is the selling agent's).
    cr_number: str = Field(default="", max_length=50)
    unified_number: str = Field(default="", max_length=50)
    # Empty: the auction's licence number.
    fal_license: str = Field(default="", max_length=100)
    manager_name: str = Text
    manager_id: str = Field(default="", max_length=20)
    manager_mobile: str = Field(default="", max_length=30)
    manager_email: str = Field(default="", max_length=200)
    crier_name: str = Text
    crier_id: str = Field(default="", max_length=20)
    crier_mobile: str = Field(default="", max_length=30)
    crier_email: str = Field(default="", max_length=200)
    # The auction.
    units_count: str = Field(default="", max_length=20)
    stream_link: str = Field(default="", max_length=500)
    receive: Literal["", "transfer", "cheque", "other"] = ""
    receive_other: str = Text
    keeping: str = Text
    receive_days: str = Field(default="", max_length=10)
    refund: Literal["", "transfer", "cheque", "other"] = ""
    refund_other: str = Text
    refund_days: str = Field(default="", max_length=10)
    entry_type: Literal["", "deposit", "advance", "refundable", "none"] = ""
    award_minutes: str = Field(default="", max_length=50)
    disposal: Literal["", "sale", "lease"] = "sale"
    contract_number: str = Field(default="", max_length=100)
    # Rights and restrictions on the auctioned property.
    rulings: list[
        Literal["none", "preemption", "session", "condition", "deposit_sale", "other"]
    ] = Field(default_factory=list, max_length=6)
    rulings_other: str = Text
    ownership: Literal["", "full", "other"] = ""
    ownership_other: str = Text
    rights: Disclosure = Field(default_factory=Disclosure)
    dispute: Disclosure = Field(default_factory=Disclosure)
    value_info: Disclosure = Field(default_factory=Disclosure)
    offplan: Disclosure = Field(default_factory=Disclosure)
    contribution: Disclosure = Field(default_factory=Disclosure)
    declarant: str = Text


class StudyForm(Structured):
    """Infath's study: what is the same for all the project's properties."""

    project_name: str = Text  # empty: the auction's name
    category: str = Field(default="", max_length=20)
    manager: str = Text


class FormsData(Structured):
    request: RequestForm = Field(default_factory=RequestForm)
    study: StudyForm = Field(default_factory=StudyForm)
    # By property id.
    properties: dict[str, PropertyForms] = Field(default_factory=dict)

    @field_validator("properties")
    @classmethod
    def few(cls, value):
        if len(value) > 1000:
            raise ValueError("Too many properties")
        return value
