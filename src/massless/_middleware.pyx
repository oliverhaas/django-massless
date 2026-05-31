"""Fast-tier middleware: a C-level chain that operates on the request header API
only (no promotion) and may short-circuit with a Response or mutate the outgoing
response's headers.

The chain is an ordered Python list compiled per route at startup. ``run_before``
runs each middleware's ``before`` in order, stopping at the first that returns a
Response (a short-circuit). ``run_after`` runs each ``after`` in reverse order so
the outermost middleware wraps last (symmetric onion ordering).
"""

import hashlib
import hmac
import time as _time
from base64 import urlsafe_b64decode

import msgspec

from massless._response cimport Response


cdef class Middleware:
    """Base fast-tier middleware.

    ``before(req)`` returns a Response to short-circuit, or None to continue.
    ``after(req, resp)`` mutates the response (e.g. adds headers); returns None.
    """

    cpdef object before(self, object req):
        return None

    cpdef object after(self, object req, Response resp):
        return None


cpdef object run_before(list chain, object req):
    """Run before() hooks in order; return the first Response or None."""
    cdef Middleware mw
    cdef object result
    for mw in chain:
        result = mw.before(req)
        if result is not None:
            return result
    return None


cpdef void run_after(list chain, object req, Response resp):
    """Run after() hooks in reverse order (onion unwinding)."""
    cdef Middleware mw
    cdef Py_ssize_t i
    for i in range(len(chain) - 1, -1, -1):
        mw = <Middleware>chain[i]
        mw.after(req, resp)


cdef class CORS(Middleware):
    """Cross-Origin Resource Sharing on the fast path.

    Answers preflight ``OPTIONS`` (with Origin + Access-Control-Request-Method)
    with a 204 carrying Access-Control-Allow-{Origin,Methods,Headers}. On a real
    request, ``after`` adds Access-Control-Allow-Origin when the Origin matches.
    """
    cdef set _origins
    cdef bint _allow_all
    cdef str _methods
    cdef str _headers

    def __init__(self, allow_origins=None, allow_methods=None, allow_headers=None):
        origins = list(allow_origins) if allow_origins is not None else []
        self._allow_all = "*" in origins
        self._origins = set(origins)
        methods = allow_methods if allow_methods is not None else ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        self._methods = ", ".join(methods)
        headers = allow_headers if allow_headers is not None else ["Authorization", "Content-Type"]
        self._headers = ", ".join(headers)

    cdef str _resolve_origin(self, object origin):
        if origin is None:
            return None
        if self._allow_all:
            return "*"
        if origin in self._origins:
            return origin
        return None

    cpdef object before(self, object req):
        cdef object origin = req.get_header("origin")
        cdef str allow
        if req.method == "OPTIONS" and req.get_header("access-control-request-method") is not None:
            allow = self._resolve_origin(origin)
            if allow is None:
                return None
            return Response(204, {
                "Access-Control-Allow-Origin": allow,
                "Access-Control-Allow-Methods": self._methods,
                "Access-Control-Allow-Headers": self._headers,
            }, b"", b"text/plain; charset=utf-8")
        return None

    cpdef object after(self, object req, Response resp):
        cdef object origin = req.get_header("origin")
        cdef str allow = self._resolve_origin(origin)
        if allow is not None:
            resp.headers["Access-Control-Allow-Origin"] = allow
        return None


cdef class RateLimit(Middleware):
    """Fixed-window per-key rate limit. Process-local state.

    ``now`` is an injectable monotonic clock (seconds, float) for deterministic
    tests. The key is read from ``key_header`` (default: a single global key).
    """
    cdef int _limit
    cdef double _window
    cdef object _now
    cdef str _key_header
    cdef str _default_key
    cdef dict _state  # key -> [window_start, count]

    def __init__(self, limit, window_s, now=None, key_header=None, default_key="__global__"):
        self._limit = limit
        self._window = float(window_s)
        self._now = now if now is not None else _time.monotonic
        self._key_header = key_header
        self._default_key = default_key
        self._state = {}

    cdef str _key(self, object req):
        cdef object value
        if self._key_header is not None:
            value = req.get_header(self._key_header)
            if value is not None:
                return value
        return self._default_key

    cpdef object before(self, object req):
        cdef str key = self._key(req)
        cdef double now = self._now()
        cdef object entry = self._state.get(key)
        cdef double start
        cdef int count
        if entry is None or (now - entry[0]) >= self._window:
            self._state[key] = [now, 1]
            return None
        start = entry[0]
        count = entry[1]
        if count >= self._limit:
            return Response(429, {"Retry-After": str(int(self._window))},
                            b"Too Many Requests", b"text/plain; charset=utf-8")
        entry[1] = count + 1
        return None


cdef bytes _b64url_decode(str segment):
    """base64url-decode a JWT segment, re-adding stripped padding."""
    cdef bytes raw = segment.encode("ascii")
    cdef int pad = (-len(raw)) % 4
    if pad:
        raw = raw + b"=" * pad
    return urlsafe_b64decode(raw)


class AuthError(Exception):
    """Internal signal for a rejected token (mapped to 401)."""


cdef class JWTAuth(Middleware):
    """HS256 JWT verification on the fast path (stdlib hmac/hashlib, no PyJWT).

    Reads ``Authorization: Bearer <jwt>``, recomputes HMAC-SHA256 over
    ``header.payload`` with the secret, constant-time compares the signature,
    checks ``exp``, decodes the claims with msgspec, and sets ``req.auth`` to the
    claims dict. No promotion. Missing/invalid/expired -> 401.
    """
    cdef bytes _secret
    cdef object _now
    cdef bint _allow_anonymous

    def __init__(self, secret, now=None, allow_anonymous=False):
        self._secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        self._now = now if now is not None else _time.time
        self._allow_anonymous = allow_anonymous

    cdef dict _verify(self, str token):
        cdef list parts = token.split(".")
        if len(parts) != 3:
            raise AuthError("malformed token")
        cdef str h_b64 = parts[0]
        cdef str p_b64 = parts[1]
        cdef str s_b64 = parts[2]
        # Verify the alg is HS256 from the header before trusting anything else.
        cdef dict header = msgspec.json.decode(_b64url_decode(h_b64))
        if header.get("alg") != "HS256":
            raise AuthError("unsupported alg")
        cdef bytes signing_input = (h_b64 + "." + p_b64).encode("ascii")
        cdef bytes expected = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        cdef bytes provided
        try:
            provided = _b64url_decode(s_b64)
        except Exception:
            raise AuthError("bad signature encoding")
        if not hmac.compare_digest(expected, provided):
            raise AuthError("signature mismatch")
        cdef dict claims = msgspec.json.decode(_b64url_decode(p_b64))
        cdef object exp = claims.get("exp")
        if exp is not None and float(exp) < self._now():
            raise AuthError("expired")
        return claims

    cpdef object before(self, object req):
        cdef object header = req.get_header("authorization")
        if header is None or not header.startswith("Bearer "):
            if self._allow_anonymous:
                req.auth = None
                return None
            return Response(401, {}, b"Unauthorized", b"text/plain; charset=utf-8")
        cdef str token = header[7:].strip()
        cdef dict claims
        try:
            claims = self._verify(token)
        except (AuthError, msgspec.DecodeError, ValueError):
            return Response(401, {}, b"Unauthorized", b"text/plain; charset=utf-8")
        req.auth = claims
        return None
