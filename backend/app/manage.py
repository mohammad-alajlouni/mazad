"""Explicit operator commands. Never print credentials."""

import argparse

from sqlalchemy import select

from .auth import hasher
from .config import settings
from .db import SessionLocal
from .models import User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["reset-admin-password"])
    parser.parse_args()
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.email == settings().admin_email.lower())
        )
        if not user:
            raise SystemExit("Administrator not found. Run bootstrap first.")
        user.password_hash = hasher.hash(settings().admin_password)
        user.token_version += 1
        db.commit()
        print("Administrator password updated. Existing sessions revoked.")


if __name__ == "__main__":
    main()
