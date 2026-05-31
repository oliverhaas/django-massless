from django.http import HttpRequest
from massless._request import MasslessRequest, RequestCore


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


def test_wrapper_delegates_and_is_httprequest():
    core = RequestCore.py_create(b"GET", b"/items/12345", b"q=hi", [(b"x-test", b"v")])
    req = MasslessRequest(core, {"item_id": 12345})
    assert isinstance(req, HttpRequest)
    assert req.method == "GET"
    assert req.path == "/items/12345"
    assert req.path_params == {"item_id": 12345}
    assert req.get_header("x-test") == "v"


def test_wrapper_does_not_promote_on_fast_path():
    core = RequestCore.py_create(b"GET", b"/", b"", [])
    req = MasslessRequest(core, {})
    # Touching a Django-machinery attribute must raise (no promotion in Phase 1).
    import pytest

    with pytest.raises(AttributeError):
        _ = req.GET
