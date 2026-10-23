from fastapi import APIRouter

from . import (
    auctions,
    banners,
    forms,
    ingestion,
    outputs,
    profile,
    projects,
    reports,
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
    reports,
):
    router.include_router(module.router)
