from massless._request import RequestCore


def test_core_method_and_path():
    core = RequestCore.py_create(b"GET", b"/items/12345", b"q=hello", [(b"x-test", b"val")])
    assert core.method == "GET"
    assert core.path == "/items/12345"


def test_core_get_header_case_insensitive():
    core = RequestCore.py_create(b"GET", b"/", b"", [(b"X-Test", b"val")])
    assert core.get_header("x-test") == "val"
    assert core.get_header("missing") is None


def test_core_query_param():
    core = RequestCore.py_create(b"GET", b"/", b"q=hello&n=3", [])
    assert core.query_param("q") == "hello"
    assert core.query_param("n") == "3"
    assert core.query_param("absent") is None
