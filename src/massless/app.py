"""Cold-path app API: registration, signature binding, route-table compile."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from massless._router import Router

if TYPE_CHECKING:
    from collections.abc import Callable

_PARAM_RE = re.compile(r"^(?P<prefix>/[^{}]*/)\{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\}$")


def build_binder(view: Callable) -> Callable[[dict, Callable], dict]:
    """Inspect a view signature and return binder(path_params, query_getter) -> kwargs.

    Path params present in path_params are coerced by annotation (int -> int).
    Remaining params are read from query_getter(name); missing optionals become None.
    """
    sig = inspect.signature(view)
    params = list(sig.parameters.values())

    def binder(path_params: dict, query_getter: Callable) -> dict:
        kwargs: dict = {}
        for p in params:
            if p.name in path_params:
                raw = path_params[p.name]
                kwargs[p.name] = int(raw) if p.annotation is int else raw
            else:
                value = query_getter(p.name)
                if value is None and p.default is not inspect.Parameter.empty:
                    value = p.default
                kwargs[p.name] = value
        return kwargs

    return binder


@dataclass
class Route:
    path: str
    view: Callable
    binder: Callable
    is_dynamic: bool
    prefix: bytes
    param_name: str | None


class MasslessAPI:
    def __init__(self) -> None:
        self.routes: list[Route] = []

    def get(self, path: str) -> Callable:
        def decorator(view: Callable) -> Callable:
            self._register(path, view)
            return view

        return decorator

    def _register(self, path: str, view: Callable) -> None:
        binder = build_binder(view)
        match = _PARAM_RE.match(path)
        if match:
            route = Route(
                path=path,
                view=view,
                binder=binder,
                is_dynamic=True,
                prefix=match["prefix"].encode("latin1"),
                param_name=match["name"],
            )
        else:
            route = Route(
                path=path,
                view=view,
                binder=binder,
                is_dynamic=False,
                prefix=path.encode("latin1"),
                param_name=None,
            )
        self.routes.append(route)

    def build_router(self) -> Router:
        router = Router()
        for route_id, route in enumerate(self.routes):
            if route.is_dynamic:
                router.add_dynamic(route.prefix, route_id)
            else:
                router.add_static(route.prefix, route_id)
        return router
