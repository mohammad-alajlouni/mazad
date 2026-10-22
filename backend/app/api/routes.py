from fastapi import APIRouter

from . import (
    auctions,
    banners,
    forms,
    ingestion,
    outputs,
    profile,
    projects,
    settings,
    social,
    users,
)

router = APIRouter()
for module in (
    profile,
    projects,
    ingestion,
    outputs,
    settings,
    auctions,
    users,
    banners,
    social,
    forms,
):
    router.include_router(module.router)
