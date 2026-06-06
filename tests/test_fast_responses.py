"""massless.JsonResponse / massless.HttpResponse are lazy HttpResponse subclasses (design
section 2.4). They carry the full response API, so they flow through any middleware, and the
body is serialized with msgspec lazily: on the clean fast path the C dispatcher calls
_serialize() (no materialization); a middleware that reads/rewrites .content materializes it.
"""

import asyncio
import json

from django.http import HttpResponse as DjangoHttpResponse
from django.test import override_settings
from django.urls import path
from massless._protocol import dispatch, parse_request

import massless
from massless.handler import MasslessHandler

# --------------------------------------------------------------------------- unit


def test_jsonresponse_is_a_django_httpresponse():
    r = massless.JsonResponse({"a": 1})
    assert isinstance(r, DjangoHttpResponse)
    assert r.streaming is False
    assert r.status_code == 200
    assert r["Content-Type"] == "application/json"


def test_jsonresponse_body_is_lazy_until_read():
    r = massless.JsonResponse({"a": 1})
    assert r._materialized is False
    # _serialize (the C path) does not materialize.
    body, ctype = r._serialize()
    assert json.loads(body) == {"a": 1}
    assert ctype == b"application/json"
    assert r._materialized is False
    # Reading .content (what a middleware does) materializes once, via msgspec.
    assert json.loads(r.content) == {"a": 1}
    assert r._materialized is True


def test_jsonresponse_header_and_cookie_api():
    r = massless.JsonResponse({"a": 1})
    r["X-Custom"] = "yes"
    r.set_cookie("sid", "abc", httponly=True)
    assert r.headers["X-Custom"] == "yes"
    assert "sid" in r.cookies
    # _serialize reflects a content-type a middleware may have changed.
    r["Content-Type"] = "application/vnd.api+json"
    _body, ctype = r._serialize()
    assert ctype == b"application/vnd.api+json"


def test_jsonresponse_content_setter_materializes():
    r = massless.JsonResponse({"a": 1})
    r.content = b"override"
    assert r._materialized is True
    assert bytes(r.content) == b"override"
    body, _ctype = r._serialize()
    assert body == b"override"


# ----------------------------------------------------------- through middleware + wire


async def fast_json_view(request):
    return massless.JsonResponse({"message": "Hello World"})


urlpatterns = [path("fj", fast_json_view)]

M = __name__
STACK = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


def _mkcore(target):
    raw = f"GET {target} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
    return parse_request(raw)


@override_settings(MIDDLEWARE=STACK, ROOT_URLCONF=M, DEBUG=False)
def test_fast_response_flows_through_real_middleware():
    handler = MasslessHandler()

    async def go():
        from massless._request import MasslessRequest

        return await handler._chain.run(MasslessRequest(_mkcore("/fj"), {}))

    resp = asyncio.run(go())
    # The middleware mutated the massless response in place (it is a real HttpResponse).
    assert resp["X-Content-Type-Options"] == "nosniff"  # SecurityMiddleware
    assert resp["X-Frame-Options"] == "DENY"  # XFrameOptionsMiddleware
    assert json.loads(bytes(resp.content)) == {"message": "Hello World"}


@override_settings(MIDDLEWARE=STACK, ROOT_URLCONF=M, DEBUG=False)
def test_fast_response_serializes_to_wire_with_middleware_headers():
    # End to end through dispatch: the fast-serialize branch must read .headers/.cookies
    # off the (mutated) HttpResponse. The retired branch read a private _headers dict; if
    # that code were still live this would error, so this also guards the rebuild.
    handler = MasslessHandler()
    raw, _keep_alive = asyncio.run(dispatch(handler, _mkcore("/fj")))
    text = raw.decode("latin1")
    assert text.startswith("HTTP/1.1 200 OK\r\n")
    assert "Content-Type: application/json\r\n" in text
    assert "X-Content-Type-Options: nosniff\r\n" in text
    assert "X-Frame-Options: DENY\r\n" in text
    body = text.split("\r\n\r\n", 1)[1]
    assert json.loads(body) == {"message": "Hello World"}


@override_settings(MIDDLEWARE=[], ROOT_URLCONF=M, DEBUG=False)
def test_fast_response_clean_fast_path_wire():
    # No middleware: the inlined fast path returns the JsonResponse, serialized via msgspec
    # without materialization.
    handler = MasslessHandler()
    assert handler._fast_ok
    raw, _ka = asyncio.run(dispatch(handler, _mkcore("/fj")))
    text = raw.decode("latin1")
    assert text.startswith("HTTP/1.1 200 OK\r\n")
    body = text.split("\r\n\r\n", 1)[1]
    assert json.loads(body) == {"message": "Hello World"}
