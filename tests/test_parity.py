import io

import pytest
from django.core.handlers.wsgi import WSGIRequest
from massless._request import MasslessRequest, RequestCore

CASES = [
    (b"GET", b"/items/5", b"q=hi&n=3", [(b"host", b"ex.com")], b""),
    (
        b"POST",
        b"/submit",
        b"",
        [(b"host", b"ex.com"), (b"content-type", b"application/x-www-form-urlencoded")],
        b"a=1&b=2",
    ),
    (b"POST", b"/api", b"", [(b"host", b"ex.com"), (b"content-type", b"application/json")], b'{"a":1}'),
    (b"GET", b"/", b"", [(b"host", b"ex.com:8080"), (b"cookie", b"sid=abc; theme=dark")], b""),
]


def _stock(method, path, query, headers, body):
    env = {
        "REQUEST_METHOD": method.decode(),
        "PATH_INFO": path.decode(),
        "QUERY_STRING": query.decode(),
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "http",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
    }
    for raw_name, raw_value in headers:
        n = raw_name.decode()
        v = raw_value.decode()
        if n == "content-type":
            env["CONTENT_TYPE"] = v
        elif n == "host":
            sn, _, sp = v.partition(":")
            env["SERVER_NAME"] = sn
            env["SERVER_PORT"] = sp or "80"
            # Real WSGI servers also pass the Host header through as HTTP_HOST
            # (it is what request.headers["Host"]/get_host() read), so the stock
            # reference must carry it too for an apples-to-apples comparison.
            env["HTTP_HOST"] = v
        else:
            env["HTTP_" + n.upper().replace("-", "_")] = v
    return WSGIRequest(env)


@pytest.mark.parametrize("case", CASES)
def test_promoted_matches_stock(case):
    stock = _stock(*case)
    req = MasslessRequest(RequestCore.py_create(*case), {})
    req._promote()
    assert req.method == stock.method
    assert req.path == stock.path
    assert dict(req.GET) == dict(stock.GET)
    assert dict(req.POST) == dict(stock.POST)
    assert req.body == stock.body
    assert req.COOKIES == stock.COOKIES
    assert req.content_type == stock.content_type
    assert req.content_params == stock.content_params
    assert req.get_host() == stock.get_host()
    assert dict(req.headers) == dict(stock.headers)
    assert req.encoding == stock.encoding
