"""The /v1 router. A slice adds its router in `build_router`, in the same change that adds the contract
operation, the leak-registry entry and the tests (see the fastapi-service skill)."""

from fastapi import APIRouter


def build_router() -> APIRouter:
    router = APIRouter(prefix="/v1")
    # router.include_router(items.router, tags=["items"])
    return router
