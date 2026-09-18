from fastapi import APIRouter

from . import banners, auctions, ingestion, outputs, projects, settings, users

router = APIRouter()
for module in (projects, ingestion, outputs, settings, auctions, users, banners):
    router.include_router(module.router)
