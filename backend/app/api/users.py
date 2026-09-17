"""Admin-managed booklet authors. No public signup or client-supplied roles."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..auth import current_admin, hasher
from ..db import get_db
from ..models import User
from .common import audit

router = APIRouter(prefix="/admin/users", dependencies=[Depends(current_admin)], tags=["users"])


class CreateUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class UserStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


def view(user):
    return {"id": user.id, "email": user.email, "role": user.role,
            "is_active": user.is_active, "created_at": user.created_at}


@router.get("")
def users(db=Depends(get_db)):
    return [view(u) for u in db.scalars(select(User).order_by(User.created_at.desc()))]


@router.post("", status_code=201)
def create_user(body: CreateUser, db=Depends(get_db)):
    user = User(email=body.email, password_hash=hasher.hash(body.password), role="user")
    db.add(user)
    audit(db, "User created", body.email)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered")
    return view(user)


@router.patch("/{id}")
def change_status(id: str, body: UserStatus, db=Depends(get_db)):
    user = db.get(User, id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == "admin":
        raise HTTPException(403, "Cannot disable an administrator")
    if user.is_active != body.is_active:
        user.is_active = body.is_active
        user.token_version += 1
        audit(db, "User status updated", user.email)
    db.commit()
    return view(user)
