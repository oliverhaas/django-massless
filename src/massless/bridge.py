"""Bridge tier: run a massless view through Django's *real* middleware chain.

Routes flagged ``bridge=True`` promote the request and dispatch through the
middleware configured in ``settings.MIDDLEWARE``. Rather than hand-roll the
onion (async/sync adaptation, ``MiddlewareNotUsed``, ``process_view`` etc.), we
subclass :class:`django.core.handlers.base.BaseHandler` and reuse its
``load_middleware`` to wrap our own innermost ``get_response`` -- one that calls
the massless view directly instead of resolving a URL. Django therefore owns
the request from entry through response, exactly as in a normal request, except
the view is the one massless matched.

We build the *async* chain (``load_middleware(is_async=True)``) because dispatch
runs inside the server's asyncio loop. Django's own ``adapt_method_mode`` wraps
any sync-only middleware with ``sync_to_async`` for us, so a sync middleware in
``settings.MIDDLEWARE`` is handled transparently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.handlers.base import BaseHandler
from django.http import HttpResponse, JsonResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest


def _to_http_response(result: object) -> HttpResponse:
    """Convert a massless view return (HttpResponse/dict/bytes/str) into an
    HttpResponse so Django's middleware chain has a real response to process."""
    if isinstance(result, HttpResponse):
        return result
    if isinstance(result, (dict, list)):
        return JsonResponse(result, safe=False)
    if isinstance(result, bytes):
        return HttpResponse(result, content_type="application/octet-stream")
    if isinstance(result, str):
        return HttpResponse(result, content_type="text/plain; charset=utf-8")
    # Fall back to JSON for other serializable objects.
    return JsonResponse(result, safe=False)


class BridgeHandler(BaseHandler):
    """A Django handler whose innermost get_response calls a massless view.

    Built once at startup. ``run(request, view, kwargs)`` stashes the matched
    view + kwargs on the request and invokes the cached middleware chain.
    """

    def __init__(self) -> None:
        # Build the async middleware chain around our overridden innermost
        # _get_response_async. load_middleware reads settings.MIDDLEWARE.
        self.load_middleware(is_async=True)

    async def _get_response_async(self, request: HttpRequest) -> HttpResponse:
        # Innermost of the chain: call the massless view instead of resolving a
        # URL. The view + kwargs were stashed by run().
        view: Callable = request._bridge_view  # type: ignore[attr-defined]  # noqa: SLF001
        kwargs: dict = request._bridge_kwargs  # type: ignore[attr-defined]  # noqa: SLF001
        result = await view(**kwargs)
        response = _to_http_response(result)
        self.check_response(response, view)
        return response

    async def run(self, request: HttpRequest, view: Callable, kwargs: dict) -> HttpResponse:
        request._bridge_view = view  # type: ignore[attr-defined]  # noqa: SLF001
        request._bridge_kwargs = kwargs  # type: ignore[attr-defined]  # noqa: SLF001
        return await self._middleware_chain(request)  # type: ignore[attr-defined]
