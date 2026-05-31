from massless._middleware import CORS, Middleware, RateLimit, run_after, run_before
from massless._request import MasslessRequest, RequestCore
from massless._response import Response


def _req(method=b"GET", path=b"/", headers=None):
    core = RequestCore.py_create(method, path, b"", headers or [], b"")
    return MasslessRequest(core, {})


# --- Task 2: base + chain runner ---


class _ShortCircuit(Middleware):
    def __init__(self, marker):
        self.marker = marker

    def before(self, req):
        return Response(418, {"X-SC": self.marker}, b"teapot", b"text/plain")


class _Recorder(Middleware):
    def __init__(self, log, name):
        self.log = log
        self.name = name

    def before(self, req):
        self.log.append(("before", self.name))

    def after(self, req, resp):
        self.log.append(("after", self.name))


def test_run_before_short_circuits_and_skips_later():
    log = []
    chain = [_Recorder(log, "a"), _ShortCircuit("hit"), _Recorder(log, "b")]
    resp = run_before(chain, _req())
    assert isinstance(resp, Response)
    assert resp.status == 418
    assert resp.headers["X-SC"] == "hit"
    # "a" ran before the short-circuit; "b" never did.
    assert log == [("before", "a")]


def test_run_before_all_none_returns_none():
    log = []
    chain = [_Recorder(log, "a"), _Recorder(log, "b")]
    assert run_before(chain, _req()) is None
    assert log == [("before", "a"), ("before", "b")]


def test_run_after_reverse_order():
    log = []
    chain = [_Recorder(log, "a"), _Recorder(log, "b")]
    resp = Response(200, {}, b"", b"application/json")
    run_after(chain, _req(), resp)
    assert log == [("after", "b"), ("after", "a")]


# --- Task 3: CORS ---


def test_cors_preflight_returns_204_with_headers():
    cors = CORS(allow_origins=["https://ex.com"])
    req = _req(
        method=b"OPTIONS",
        headers=[(b"origin", b"https://ex.com"), (b"access-control-request-method", b"GET")],
    )
    resp = cors.before(req)
    assert isinstance(resp, Response)
    assert resp.status == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "https://ex.com"
    assert "GET" in resp.headers["Access-Control-Allow-Methods"]
    assert "Access-Control-Allow-Headers" in resp.headers


def test_cors_non_preflight_before_is_none_and_after_adds_header():
    cors = CORS(allow_origins=["https://ex.com"])
    req = _req(headers=[(b"origin", b"https://ex.com")])
    assert cors.before(req) is None
    resp = Response(200, {}, b"{}", b"application/json")
    cors.after(req, resp)
    assert resp.headers["Access-Control-Allow-Origin"] == "https://ex.com"


def test_cors_origin_mismatch_adds_nothing():
    cors = CORS(allow_origins=["https://ex.com"])
    req = _req(headers=[(b"origin", b"https://evil.com")])
    resp = Response(200, {}, b"{}", b"application/json")
    cors.after(req, resp)
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_cors_no_promotion():
    cors = CORS(allow_origins=["https://ex.com"])
    req = _req(headers=[(b"origin", b"https://ex.com")])
    cors.before(req)
    resp = Response(200, {}, b"{}", b"application/json")
    cors.after(req, resp)
    assert req._is_django is False


# --- Task 4: RateLimit ---


class _FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_rate_limit_allows_then_429():
    clock = _FakeClock()
    rl = RateLimit(limit=2, window_s=60, now=clock)
    req = _req()
    assert rl.before(req) is None  # 1
    assert rl.before(req) is None  # 2
    blocked = rl.before(req)  # 3 -> 429
    assert isinstance(blocked, Response)
    assert blocked.status == 429


def test_rate_limit_window_reset():
    clock = _FakeClock()
    rl = RateLimit(limit=2, window_s=60, now=clock)
    req = _req()
    rl.before(req)
    rl.before(req)
    assert rl.before(req).status == 429
    clock.advance(60)  # window elapsed
    assert rl.before(req) is None  # allowed again
    assert req._is_django is False
