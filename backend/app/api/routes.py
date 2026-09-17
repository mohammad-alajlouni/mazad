from fastapi import APIRouter

from . import auctions, ingestion, outputs, projects, settings, users

router = APIRouter()
for module in (projects, ingestion, outputs, settings, auctions, users):
    router.include_router(module.router)
