"""The cross-tenant leak fixture's machinery. The product's cases live in `leak_registry.py`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

if TYPE_CHECKING:
    from tests.conftest import World

IGNORED_METHODS = {"HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Request:
    """A concrete request, made as tenant A, that uses tenant B's ids."""

    method: str
    path: str
    json: Any = None
    headers: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class RouteCase:
    """One route. `expect="denied"`: the answer is 403 or 404. `expect="no_leak"`: the answer may
    succeed, but must contain none of tenant B's ids."""

    method: str
    path: str  # the route's path template, exactly as the app declares it
    build: Callable[[World], Request]
    expect: Literal["denied", "no_leak"] = "denied"


@dataclass(frozen=True)
class Exempt:
    """A route that cannot leak by construction. Every exemption has its own reason."""

    method: str
    path: str
    reason: str


@dataclass(frozen=True)
class JobCase:
    """One job type. `run` calls the job as tenant A with tenant B's ids and must raise, or do nothing."""

    name: str
    run: Callable[[World], Awaitable[None]]


def served_routes(app: FastAPI) -> set[tuple[str, str]]:
    """Every (method, path template) the app serves under /v1, including routes hidden from the OpenAPI
    document (FastAPI 0.162 includes routers lazily, so the flat list comes from `iter_route_contexts`)."""
    found: set[tuple[str, str]] = set()
    for ctx in iter_route_contexts(app.routes):
        path = ctx.path or ""
        if path.startswith("/v1"):
            found.update((m, path) for m in (ctx.methods or set()) - IGNORED_METHODS)
    return found


def coverage_problems(
    served: Iterable[tuple[str, str]], cases: Iterable[RouteCase], exempt: Iterable[Exempt]
) -> list[str]:
    """Problems with the registry: a served route without a case or a reasoned exemption, an
    exemption without a reason, an entry for a route that does not exist."""
    served_set = set(served)
    case_keys = {(c.method, c.path) for c in cases}
    exempt_list = list(exempt)
    exempt_keys = {(e.method, e.path) for e in exempt_list}
    problems: list[str] = []
    for method, path in sorted(served_set - case_keys - exempt_keys):
        problems.append(f"route not in the leak registry: {method} {path}")
    for e in exempt_list:
        if not e.reason.strip():
            problems.append(f"exemption without a reason: {e.method} {e.path}")
    for method, path in sorted((case_keys | exempt_keys) - served_set):
        problems.append(f"leak registry entry for a route that does not exist: {method} {path}")
    for key in sorted(case_keys & exempt_keys):
        problems.append(f"route both covered and exempt: {key[0]} {key[1]}")
    return problems
