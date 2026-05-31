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
    assert raw == (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 7\r\n"
        b"Connection: keep-alive\r\n"
        b"\r\n"
        b'{"a":1}'
    )


def test_build_http_response_404_close():
    raw = _response.build_http_response(404, b"text/plain; charset=utf-8", b"nope", False)
    assert raw.startswith(b"HTTP/1.1 404 Not Found\r\n")
    assert b"Connection: close\r\n" in raw
    assert raw.endswith(b"\r\n\r\nnope")
