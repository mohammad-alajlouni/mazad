from fastapi import APIRouter

from . import auctions, ingestion, outputs, projects, settings

router = APIRouter()
for module in (projects, ingestion, outputs, settings, auctions):
    router.include_router(module.router)
