"""The /v1 router (example overlay: adds the items slice)."""

from fastapi import APIRouter

from app.routes.v1 import items


def build_router() -> APIRouter:
    router = APIRouter(prefix="/v1")
    router.include_router(items.router, tags=["items"])
    return router
