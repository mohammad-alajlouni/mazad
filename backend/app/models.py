import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

JSONType = JSON().with_variant(JSONB(), "postgresql")
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Record, Base):
    __tablename__ = "users"
    agent_profile: Mapped[dict] = mapped_column(JSONType, default=dict, server_default="{}")
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )


class Project(Record, Base):
    __tablename__ = "projects"
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    workspace_type: Mapped[str] = mapped_column(
        String(20), default="project", server_default="project"
    )
    banner_config: Mapped[dict] = mapped_column(
        JSONType, default=dict, server_default="{}"
    )
    social_config: Mapped[dict] = mapped_column(
        JSONType, default=dict, server_default="{}"
    )
    auction: Mapped[dict] = mapped_column(JSONType, default=dict)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(100), unique=True)
    customer: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[str] = mapped_column(String(20), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    revision: Mapped[int] = mapped_column(Integer, default=0)


class ProjectItem(Record, Base):
    __tablename__ = "project_items"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    property_data: Mapped[dict] = mapped_column(JSONType, default=dict)
    title: Mapped[str] = mapped_column(String(300))
    reference: Mapped[str] = mapped_column(String(100), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    specifications: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), default=1)
    financial_value: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    technical_information: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    attributes: Mapped[dict] = mapped_column(JSONType, default=dict)


class SellingAgent(Record, Base):
    __tablename__ = "selling_agents"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)


class RentalContract(Record, Base):
    __tablename__ = "rental_contracts"
    item_id: Mapped[str] = mapped_column(ForeignKey("project_items.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict] = mapped_column(JSONType, default=dict)


class ProjectImage(Record, Base):
    __tablename__ = "project_images"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    item_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_items.id"), nullable=True
    )
    key: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), default="additional")
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str] = mapped_column(String(300), default="")
    orientation: Mapped[str] = mapped_column(String(20), default="landscape")


class ExcelImport(Record, Base):
    __tablename__ = "excel_imports"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    filename: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PREVIEW")


class ExcelImportRow(Record, Base):
    __tablename__ = "excel_import_rows"
    import_id: Mapped[str] = mapped_column(ForeignKey("excel_imports.id"), index=True)
    sheet: Mapped[str] = mapped_column(String(200))
    row_number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    errors: Mapped[list] = mapped_column(JSONType, default=list)


class Template(Record, Base):
    __tablename__ = "templates"
    output_type: Mapped[str] = mapped_column(String(100), unique=True)
    config: Mapped[dict] = mapped_column(JSONType, default=dict)


class GeneratedOutput(Record, Base):
    __tablename__ = "generated_outputs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    output_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    content: Mapped[dict] = mapped_column(JSON)
    template_id: Mapped[str] = mapped_column(ForeignKey("templates.id"))
    revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GeneratedFile(Record, Base):
    __tablename__ = "generated_files"
    output_id: Mapped[str] = mapped_column(
        ForeignKey("generated_outputs.id"), index=True
    )
    key: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(100))


class AIGeneration(Record, Base):
    __tablename__ = "ai_generations"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    purpose: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text, default="")


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default="global")
    data: Mapped[dict] = mapped_column(JSONType, default=dict)


class AuditLog(Record, Base):
    __tablename__ = "audit_logs"
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
