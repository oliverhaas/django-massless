"""Cold-path app API: registration, signature binding, route-table compile."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


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
