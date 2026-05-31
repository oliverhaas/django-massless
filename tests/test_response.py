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
