from fastapi import APIRouter

from . import social, banners, auctions, ingestion, outputs, projects, settings, users

router = APIRouter()
for module in (projects, ingestion, outputs, settings, auctions, users, banners, social):
    router.include_router(module.router)
