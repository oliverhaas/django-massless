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


def _make_jwt_with_segments(header_obj, payload_obj, secret: str) -> str:
    """Build a token where the header/payload may be arbitrary JSON (not objects).

    Mirrors ``make_jwt`` but lets the caller substitute a non-object header or
    payload (e.g. a JSON array) to exercise the malformed-segment path.
    """
    header = _b64url(json.dumps(header_obj).encode())
    payload = _b64url(json.dumps(payload_obj).encode())
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


def test_alg_none_rejected_401():
    # alg-confusion / alg:none bypass: a token declaring "none" must be rejected
    # before any signature handling.
    secret = "s"
    token = make_jwt({"sub": "42", "exp": time.time() + 3600}, secret, alg="none")
    assert JWTAuth(secret=secret).before(_req_with_auth(token)).status == 401


def test_alg_confusion_hs512_rejected_401():
    # Only HS256 is accepted; a different HMAC alg must be rejected even if the
    # attacker correctly HMAC'd with the secret (the header alg must match).
    secret = "s"
    token = make_jwt({"sub": "42", "exp": time.time() + 3600}, secret, alg="HS512")
    assert JWTAuth(secret=secret).before(_req_with_auth(token)).status == 401


def test_future_nbf_rejected_401():
    secret = "s"
    token = make_jwt({"sub": "1", "exp": 5000, "nbf": 3000}, secret)
    # now=2000 is before nbf=3000 -> not yet valid.
    assert JWTAuth(secret=secret, now=lambda: 2000.0).before(_req_with_auth(token)).status == 401
    # now=3500 is after nbf and before exp -> valid.
    assert JWTAuth(secret=secret, now=lambda: 3500.0).before(_req_with_auth(token)) is None


def test_non_object_header_json_array_401():
    # Regression: a header segment that is valid JSON but not an object (e.g. a
    # JSON array) must yield a 401 Response, not raise (which would propagate to
    # a 500). The header is decoded before any signature check, so this is an
    # unauthenticated-attacker reachable path.
    secret = "s"
    token = _make_jwt_with_segments([1, 2, 3], {"sub": "42"}, secret)
    mw = JWTAuth(secret=secret)
    resp = mw.before(_req_with_auth(token))
    assert isinstance(resp, Response)
    assert resp.status == 401


def test_non_object_payload_json_array_401():
    # Regression: a payload segment that is valid JSON but not an object must
    # also yield a 401 Response (not raise). Use a valid HS256 header so the
    # signature passes and we reach the payload decode.
    secret = "s"
    token = _make_jwt_with_segments({"alg": "HS256", "typ": "JWT"}, [1, 2, 3], secret)
    mw = JWTAuth(secret=secret)
    resp = mw.before(_req_with_auth(token))
    assert isinstance(resp, Response)
    assert resp.status == 401


def test_missing_exp_is_accepted():
    # Documented policy: a token with no `exp` does not expire (matches common JWT libs).
    secret = "s"
    token = make_jwt({"sub": "7"}, secret)
    req = _req_with_auth(token)
    assert JWTAuth(secret=secret).before(req) is None
    assert req.auth["sub"] == "7"
