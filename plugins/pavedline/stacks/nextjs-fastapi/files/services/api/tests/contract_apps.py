"""Apps for the contract_check tests: factories importable as `tests.contract_apps:<name>`.

They are bare FastAPI apps, so the script is tested on its own and the tests do not depend on which
slices a product has built.
"""

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel


class Widget(BaseModel):
    id: str
    label: str


class WidgetEnvelope(BaseModel):
    data: Widget


def plain() -> FastAPI:
    return FastAPI()


def with_extra_route() -> FastAPI:
    """The app serves an operation the contract does not describe."""
    router = APIRouter(prefix="/v1")

    @router.get("/widgets")
    async def list_widgets() -> dict[str, list[str]]:
        return {"data": []}

    app = FastAPI()
    app.include_router(router)
    return app


def with_widget_fields() -> FastAPI:
    router = APIRouter(prefix="/v1")

    @router.get("/widgets/{widget_id}")
    async def get_widget(widget_id: str) -> WidgetEnvelope:
        return WidgetEnvelope(data=Widget(id=widget_id, label="x"))

    app = FastAPI()
    app.include_router(router)
    return app
