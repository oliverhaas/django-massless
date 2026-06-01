from massless import _response


def test_serialize_dict_is_json():
    body, ctype = _response.serialize_body({"message": "Hello World"})
    assert body == b'{"message":"Hello World"}'
    assert ctype == b"application/json"


def test_serialize_list_is_json():
    body, ctype = _response.serialize_body([1, 2, 3])
    assert body == b"[1,2,3]"
    assert ctype == b"application/json"


def test_serialize_str_is_text():
    body, ctype = _response.serialize_body("hi")
    assert body == b"hi"
    assert ctype == b"text/plain; charset=utf-8"


def test_serialize_bytes_passthrough():
    body, ctype = _response.serialize_body(b"\x00\x01")
    assert body == b"\x00\x01"
    assert ctype == b"application/octet-stream"


def test_build_http_response_200_keepalive():
    raw = _response.build_http_response(200, b"application/json", b'{"a":1}', True)
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert b"Content-Type: application/json\r\n" in raw
    assert b"Content-Length: 7\r\n" in raw
    # Keep-alive is the HTTP/1.1 default; no Connection header is emitted (uvicorn parity).
    assert b"Connection:" not in raw
    assert b"Date: " in raw
    assert raw.endswith(b"\r\n\r\n" + b'{"a":1}')


def test_build_http_response_404_close():
    raw = _response.build_http_response(404, b"text/plain; charset=utf-8", b"nope", False)
    assert raw.startswith(b"HTTP/1.1 404 Not Found\r\n")
    assert b"Connection: close\r\n" in raw
    assert raw.endswith(b"\r\n\r\nnope")


def test_response_attrs():
    resp = _response.Response(200, {"X-A": "1"}, b"hi")
    assert resp.status == 200
    assert resp.headers == {"X-A": "1"}
    assert resp.body == b"hi"


def _strip_date(raw):
    return b"\r\n".join(line for line in raw.split(b"\r\n") if not line.startswith(b"Date:"))


def test_response_to_bytes_matches_build_http_response():
    # A Response with no extra headers produces the same wire bytes as build_http_response
    # (ignoring the Date header, which is keyed to the wall clock).
    resp = _response.Response(200, {}, b'{"a":1}', b"application/json")
    raw = _response.response_to_bytes(resp, True)
    assert _strip_date(raw) == _strip_date(_response.build_http_response(200, b"application/json", b'{"a":1}', True))


def test_response_to_bytes_appends_headers():
    resp = _response.Response(204, {"X-A": "1", "X-B": "2"}, b"", b"text/plain; charset=utf-8")
    raw = resp.to_bytes(True)
    assert raw.startswith(b"HTTP/1.1 204 No Content\r\n")
    assert b"X-A: 1\r\n" in raw
    assert b"X-B: 2\r\n" in raw
    assert raw.endswith(b"\r\n\r\n")


def test_from_view_result_dict():
    resp = _response.Response.from_view_result({"message": "Hello World"})
    assert resp.status == 200
    assert resp.body == b'{"message":"Hello World"}'
    assert resp.content_type == b"application/json"


def test_from_view_result_str_and_bytes():
    r1 = _response.Response.from_view_result("hi")
    assert r1.body == b"hi"
    assert r1.content_type == b"text/plain; charset=utf-8"
    r2 = _response.Response.from_view_result(b"\x00\x01")
    assert r2.body == b"\x00\x01"
    assert r2.content_type == b"application/octet-stream"
