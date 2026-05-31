import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64encode

from massless._middleware import JWTAuth
from massless._request import MasslessRequest, RequestCore
from massless._response import Response


def _b64url(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_jwt(claims: dict, secret: str, alg: str = "HS256") -> str:
    """Build an HS256 JWT with stdlib only (no PyJWT)."""
    header = _b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


def _req_with_auth(token: str | None):
    headers = []
    if token is not None:
        headers.append((b"authorization", b"Bearer " + token.encode()))
    core = RequestCore.py_create(b"GET", b"/auth", b"", headers, b"")
    return MasslessRequest(core, {})


def test_valid_token_sets_auth_no_short_circuit():
    secret = "s"
    token = make_jwt({"sub": "42", "exp": time.time() + 3600}, secret)
    mw = JWTAuth(secret=secret)
    req = _req_with_auth(token)
    assert mw.before(req) is None
    assert req.auth["sub"] == "42"
    # No promotion: reading/setting request.auth stays on the fast path.
    assert req._is_django is False


def test_tampered_signature_401():
    secret = "s"
    token = make_jwt({"sub": "42", "exp": time.time() + 3600}, secret)
    # Flip a char in the signature segment.
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}"
    mw = JWTAuth(secret=secret)
    resp = mw.before(_req_with_auth(tampered))
    assert isinstance(resp, Response)
    assert resp.status == 401


def test_wrong_secret_401():
    token = make_jwt({"sub": "42", "exp": time.time() + 3600}, "right")
    mw = JWTAuth(secret="wrong")
    assert mw.before(_req_with_auth(token)).status == 401


def test_expired_token_401():
    secret = "s"
    token = make_jwt({"sub": "42", "exp": time.time() - 10}, secret)
    mw = JWTAuth(secret=secret)
    resp = mw.before(_req_with_auth(token))
    assert isinstance(resp, Response)
    assert resp.status == 401


def test_missing_header_401():
    mw = JWTAuth(secret="s")
    resp = mw.before(_req_with_auth(None))
    assert isinstance(resp, Response)
    assert resp.status == 401


def test_allow_anonymous_passes_with_no_header():
    mw = JWTAuth(secret="s", allow_anonymous=True)
    req = _req_with_auth(None)
    assert mw.before(req) is None
    assert req.auth is None
    assert req._is_django is False


def test_injected_clock_for_exp():
    secret = "s"
    # exp is at t=2000; with now() returning 1500 it's valid, 2500 it's expired.
    token = make_jwt({"sub": "1", "exp": 2000}, secret)
    valid = JWTAuth(secret=secret, now=lambda: 1500.0)
    assert valid.before(_req_with_auth(token)) is None
    expired = JWTAuth(secret=secret, now=lambda: 2500.0)
    assert expired.before(_req_with_auth(token)).status == 401
