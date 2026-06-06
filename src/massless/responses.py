"""Optional fast-tier responses: lazy ``HttpResponse`` subclasses.

Plain Django views keep returning ``django.http`` responses (handled unchanged). For hot
endpoints, return one of these instead: the body is serialized with msgspec, and on the
clean fast path the C dispatcher serializes it directly (no ``json.dumps``, no Django body
re-fold). They ARE real ``HttpResponse`` subclasses, so they carry the full response API
(``headers``/``cookies``/``content``/``streaming``) and flow correctly through any
middleware: a middleware that reads or rewrites ``.content`` (gzip, conditional-get)
materializes the body via msgspec on first touch and from then on behaves like a normal
``HttpResponse``. Opt in per view; lose nothing for the rest.

    from massless import JsonResponse

    async def view(request):
        return JsonResponse({"hello": "world"})
"""

from __future__ import annotations

from django.http import HttpResponse as _DjangoHttpResponse
from django.http.response import HttpResponseBase

from massless._response import serialize_body


class _Fast(_DjangoHttpResponse):
    """Marker base for massless opt-in fast responses.

    The C dispatcher recognizes ``_Fast`` to call ``_serialize()`` (msgspec) instead of
    re-reading a Django body. Subclasses are real ``HttpResponse`` objects, so any middleware
    that touches the response through the standard API just works.
    """

    # JsonResponse flips this to False until its body is materialized; a plain massless
    # HttpResponse holds eager bytes and is always "materialized".
    _materialized = True

    def _content_type_bytes(self) -> bytes:
        ct = self.headers.get("Content-Type", "")
        return ct.encode("latin1") if isinstance(ct, str) else (ct or b"")

    def _serialize(self) -> tuple[bytes, bytes]:
        """Return (body_bytes, content_type_bytes) for the C serializer."""
        return bytes(self.content), self._content_type_bytes()


class JsonResponse(_Fast):
    """A JSON response serialized with msgspec, lazily.

    The body is not encoded until something reads ``.content`` (msgspec, once) or the C
    serializer calls ``_serialize()`` on the clean fast path (msgspec, no materialization).
    """

    def __init__(self, data: object, status: int = 200) -> None:
        # Initialize through HttpResponseBase (sets headers/cookies/status/Content-Type) and
        # deliberately skip HttpResponse.__init__, which would eagerly encode the body.
        HttpResponseBase.__init__(self, content_type="application/json", status=status)
        self.data = data
        self._materialized = False

    @property
    def content(self) -> bytes:
        if not self._materialized:
            body, _ctype = serialize_body(self.data)
            self._container = [body]
            self._materialized = True
        return b"".join(self._container)

    @content.setter
    def content(self, value: object) -> None:
        # A middleware rewriting the body (gzip etc.) materializes us; defer to Django's setter.
        _DjangoHttpResponse.content.fset(self, value)  # type: ignore[attr-defined]
        self._materialized = True

    def _serialize(self) -> tuple[bytes, bytes]:
        if not self._materialized:
            body, _ctype = serialize_body(self.data)
            return body, self._content_type_bytes()
        return bytes(self.content), self._content_type_bytes()


class HttpResponse(_Fast):
    """A raw bytes/str body with an explicit content type, serialized at the C layer.

    A plain ``django.http.HttpResponse`` works just as well under massless; this exists for
    symmetry with ``JsonResponse`` and as an explicit opt-in marker.
    """

    def __init__(
        self,
        content: bytes | str = b"",
        content_type: str = "application/octet-stream",
        status: int = 200,
    ) -> None:
        _DjangoHttpResponse.__init__(self, content=content, content_type=content_type, status=status)
