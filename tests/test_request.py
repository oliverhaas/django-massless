import pytest
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
    # Touching a Django-machinery attribute promotes (Phase 2). Before any access
    # the latch is unset; here we only assert it does NOT promote at construction.
    assert req._is_django is False


# --- Task 1: RequestCore carries the body ---
def test_core_exposes_body():
    core = RequestCore.py_create(
        b"POST",
        b"/x",
        b"",
        [(b"content-type", b"application/json")],
        b'{"a":1}',
    )
    assert core.body == b'{"a":1}'


# --- Task 2: plain method/path attributes ---
def test_method_path_are_plain_attributes_and_settable():
    core = RequestCore.py_create(b"GET", b"/items/5", b"", [], b"")
    req = MasslessRequest(core, {})
    assert req.method == "GET"
    assert req.path == "/items/5"
    req.path = "/changed"  # plain attr: assignable (read-only property would raise)
    assert req.path == "/changed"


# --- Task 3: build a WSGI environ from the core ---
def test_build_wsgi_environ_maps_core():
    core = RequestCore.py_create(
        b"POST",
        b"/items/5",
        b"q=hi",
        [(b"host", b"example.com:9000"), (b"content-type", b"application/json"), (b"x-test", b"v")],
        b'{"a":1}',
    )
    req = MasslessRequest(core, {})
    env = req._build_wsgi_environ()
    assert env["REQUEST_METHOD"] == "POST"
    assert env["PATH_INFO"] == "/items/5"
    assert env["QUERY_STRING"] == "q=hi"
    assert env["CONTENT_TYPE"] == "application/json"
    assert env["CONTENT_LENGTH"] == "7"
    assert env["HTTP_X_TEST"] == "v"
    assert env["SERVER_NAME"] == "example.com"
    assert env["SERVER_PORT"] == "9000"
    assert env["wsgi.input"].read() == b'{"a":1}'


# --- Task 4: promotion via WSGIRequest.__init__ + __getattr__ ---
def test_promote_populates_django_state():
    core = RequestCore.py_create(b"GET", b"/items/5", b"q=hi", [(b"host", b"ex.com")], b"")
    req = MasslessRequest(core, {})
    assert req._is_django is False
    assert req.GET["q"] == "hi"  # __getattr__ miss -> promote
    assert req._is_django is True
    assert req.META["REQUEST_METHOD"] == "GET"


def test_promotion_is_idempotent():
    core = RequestCore.py_create(b"GET", b"/", b"", [(b"host", b"ex.com")], b"")
    req = MasslessRequest(core, {})
    _ = req.GET
    meta1 = req.META
    _ = req.COOKIES
    assert req.META is meta1  # not rebuilt


def test_getattr_recursion_guard_clean_attributeerror():
    core = RequestCore.py_create(b"GET", b"/", b"", [(b"host", b"ex.com")], b"")
    req = MasslessRequest(core, {})
    # A genuinely missing attr after promotion must raise cleanly, not recurse.
    with pytest.raises(AttributeError):
        _ = req.nonexistent_attr
    assert req._is_django is True
    with pytest.raises(AttributeError):
        _ = req.still_missing


# --- Task 5: bounded property/method overrides ---
@pytest.mark.parametrize(
    "access",
    [
        lambda r: r.body,
        lambda r: r.headers["X-Test"],
        lambda r: r.get_host(),
        lambda r: r.scheme,
    ],
)
def test_property_access_promotes(access):
    core = RequestCore.py_create(
        b"GET",
        b"/",
        b"",
        [(b"host", b"ex.com"), (b"x-test", b"v")],
        b"",
    )
    req = MasslessRequest(core, {})
    access(req)
    assert req._is_django is True


def test_body_returns_bytes_after_promote():
    core = RequestCore.py_create(
        b"POST",
        b"/",
        b"",
        [(b"host", b"ex.com"), (b"content-type", b"text/plain")],
        b"hello",
    )
    req = MasslessRequest(core, {})
    assert req.body == b"hello"
