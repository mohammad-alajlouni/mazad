from sqlalchemy import select

from .auth import hasher
from .config import settings
from .db import SessionLocal
from .generation.generators import GENERATORS
from .models import SystemSetting, Template, User
from .schemas import Branding


def bootstrap():
    with SessionLocal() as db:
        admin = db.scalar(
            select(User).where(User.email == settings().admin_email.lower())
        )
        if not admin:
            db.add(
                User(
                    email=settings().admin_email.lower(),
                    password_hash=hasher.hash(settings().admin_password),
                    role="admin",
                )
            )
        else:
            admin.role = "admin"
        for key in GENERATORS:
            if not db.scalar(select(Template).where(Template.output_type == key)):
                db.add(
                    Template(
                        output_type=key,
                        config={"file": key + ".html", "demo": True, "version": 1},
                    )
                )
        if not db.get(SystemSetting, "global"):
            db.add(SystemSetting(id="global", data=Branding().model_dump()))
        db.commit()


if __name__ == "__main__":
    bootstrap()
