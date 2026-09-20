from fastapi import APIRouter

from . import profile, social, banners, auctions, ingestion, outputs, projects, settings, users

router = APIRouter()
for module in (profile, projects, ingestion, outputs, settings, auctions, users, banners, social):
    router.include_router(module.router)
