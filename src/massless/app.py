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


def build_binder(view: Callable) -> Callable[[object, dict, Callable], dict]:
    """Inspect a view signature and return binder(request, path_params, query_getter) -> kwargs.

    A parameter named ``request`` is bound to the injected request object and is
    never treated as a path or query param. Path params present in path_params are
    coerced by annotation (int -> int). Remaining params are read from
    query_getter(name); missing optionals become None.
    """
    sig = inspect.signature(view)
    params = list(sig.parameters.values())

    def binder(request: object, path_params: dict, query_getter: Callable) -> dict:
        kwargs: dict = {}
        for p in params:
            if p.name == "request":
                kwargs["request"] = request
            elif p.name in path_params:
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
    middleware: list  # compiled fast-tier chain (global defaults + per-route), in order
    bridge: bool  # run the view through Django's real middleware chain


class MasslessAPI:
    def __init__(self, middleware: list | None = None) -> None:
        self.routes: list[Route] = []
        # Global default fast-tier middleware, prepended to every route's chain.
        self.middleware: list = list(middleware) if middleware is not None else []

    def get(self, path: str, middleware: list | None = None, bridge: bool = False) -> Callable:  # noqa: FBT001, FBT002
        def decorator(view: Callable) -> Callable:
            self._register(path, view, middleware=middleware, bridge=bridge)
            return view

        return decorator

    def _register(
        self,
        path: str,
        view: Callable,
        middleware: list | None = None,
        bridge: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        binder = build_binder(view)
        # Compile the per-route chain: global defaults first, then route-specific.
        chain = [*self.middleware, *(middleware or [])]
        match = _PARAM_RE.match(path)
        if match:
            route = Route(
                path=path,
                view=view,
                binder=binder,
                is_dynamic=True,
                prefix=match["prefix"].encode("latin1"),
                param_name=match["name"],
                middleware=chain,
                bridge=bridge,
            )
        else:
            route = Route(
                path=path,
                view=view,
                binder=binder,
                is_dynamic=False,
                prefix=path.encode("latin1"),
                param_name=None,
                middleware=chain,
                bridge=bridge,
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
