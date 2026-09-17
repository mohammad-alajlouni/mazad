import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from pydantic import BaseModel, Field
from sqlalchemy import select

from .config import settings
from .db import get_db
from .models import User

router = APIRouter(prefix="/auth", tags=["authentication"])
hasher = PasswordHash.recommended()
attempts = defaultdict(deque)


class Login(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1024)


def current_user(request: Request, db=Depends(get_db)):
    try:
        claims = jwt.decode(
            request.cookies.get("session", ""),
            settings().jwt_secret,
            algorithms=["HS256"],
        )
        user = db.get(User, claims["sub"])
        if not user or claims.get("version") != user.token_version:
            raise ValueError()
        db.info["user_id"] = user.id
        return user
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, "Please sign in")


@router.post("/login")
def login(body: Login, request: Request, response: Response, db=Depends(get_db)):
    key = request.client.host if request.client else "unknown"
    queue = attempts[key]
    timestamp = time.monotonic()
    while queue and queue[0] < timestamp - 300:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, "Too many login attempts. Try again in five minutes.")
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not hasher.verify(body.password, user.password_hash):
        queue.append(timestamp)
        logging.warning("Authentication failed")
        raise HTTPException(401, "Invalid email or password")
    queue.clear()
    token = jwt.encode(
        {
            "sub": user.id,
            "version": user.token_version,
            "exp": datetime.now(timezone.utc) + timedelta(hours=8),
        },
        settings().jwt_secret,
        algorithm="HS256",
    )
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        max_age=28800,
        path="/",
    )
    return {"email": user.email}


@router.get("/me")
def me(user=Depends(current_user)):
    return {"email": user.email}


@router.post("/logout")
def logout(response: Response, user=Depends(current_user), db=Depends(get_db)):
    user.token_version += 1
    db.commit()
    response.delete_cookie("session", path="/")
    return {"ok": True}
