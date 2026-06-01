import time
from email.utils import formatdate
from http import HTTPStatus

import msgspec


cpdef tuple serialize_body(object obj):
    """Return (body_bytes, content_type_bytes) for a view return value."""
    if isinstance(obj, bytes):
        return obj, b"application/octet-stream"
    if isinstance(obj, str):
        return (<str>obj).encode("utf-8"), b"text/plain; charset=utf-8"
    return msgspec.json.encode(obj), b"application/json"


# Full IANA reason-phrase table (matches uvicorn's STATUS_LINE / http.client.responses),
# so a 302/201/405/503 serializes with its real phrase, not a placeholder "OK".
cdef dict _REASON = {int(s): s.phrase.encode("ascii") for s in HTTPStatus}
cdef bytes _UNKNOWN_REASON = b"Unknown Status Code"


# RFC 7231 Date header, refreshed at most once per wall-clock second (as uvicorn does in
# Server.on_tick) so the formatdate cost is amortized across every request in that second.
cdef bytes _date_value = b""
cdef long _date_epoch = -1


cdef bytes _http_date():
    global _date_value, _date_epoch
    cdef long now = <long>time.time()
    if now != _date_epoch:
        _date_value = formatdate(now, usegmt=True).encode("ascii")
        _date_epoch = now
    return _date_value


cpdef bytes build_http_response(int status, bytes content_type, bytes body, bint keep_alive, bytes method=b"GET"):
    cdef bytes reason = _REASON.get(status, _UNKNOWN_REASON)
    cdef bint is_head = method == b"HEAD"
    cdef bint bodyless = status == 204 or status == 304
    cdef list parts = [b"HTTP/1.1 " + str(status).encode("ascii") + b" " + reason + b"\r\n"]
    if content_type:
        parts.append(b"Content-Type: " + content_type + b"\r\n")
    parts.append(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n")
    if not keep_alive:
        # Keep-alive is the HTTP/1.1 default and emitted implicitly (uvicorn parity); only
        # an explicit close is signalled on the wire.
        parts.append(b"Connection: close\r\n")
    parts.append(b"Date: " + _http_date() + b"\r\n")
    parts.append(b"\r\n")
    if not is_head and not bodyless:
        parts.append(body)
    return b"".join(parts)


cpdef bytes reason_phrase(int status):
    return _REASON.get(status, _UNKNOWN_REASON)


cdef class Response:
    """A lightweight response value for fast-tier middleware.

    Carries a status, an ordered header dict (name -> value, both str), and a
    bytes body. Used for middleware short-circuits (preflight 204, 401, 429) and
    as the wrapper a view return is folded into so ``after()`` hooks can mutate
    headers before the C serializer emits the wire bytes.

    Fields are declared in _response.pxd so other extensions can cimport them.
    """

    def __init__(self, int status, dict headers=None, bytes body=b"",
                 bytes content_type=b"application/octet-stream", bytes reason=b""):
        self.status = status
        self.headers = dict(headers) if headers is not None else {}
        # Set-Cookie cannot live in `headers` (a dict can't hold repeats); the
        # bridge appends each cookie's OutputString() here, emitted one line each.
        self.cookies = []
        self.body = body if body is not None else b""
        self.content_type = content_type
        self.reason = reason
        # Whether the source carried a Content-Type at all. A truthy content_type
        # implies present; the bridge sets this True for a present-but-empty type so
        # to_bytes can tell it apart from a genuinely absent one (e.g. a 304).
        self.ct_present = bool(content_type)

    @staticmethod
    def from_view_result(object obj):
        """Build a Response (200) from a view's dict/bytes/str return value."""
        cdef bytes body
        cdef bytes ctype
        body, ctype = serialize_body(obj)
        return Response(200, {}, body, ctype)

    cpdef bytes to_bytes(self, bint keep_alive, bytes method=b"GET"):
        """Serialize to HTTP/1.1 wire bytes, appending any extra headers.

        Honors HEAD (headers only, no body), 204/304 (no Content-Length/body, and 304
        carries no Content-Type), the exact Django reason phrase, an implicit-keep-alive
        Connection policy, and a once-per-second Date header.
        """
        cdef bytes reason = self.reason if self.reason else _REASON.get(self.status, _UNKNOWN_REASON)
        cdef bint is_head = method == b"HEAD"
        # 204/304 carry no message body. Django's CommonMiddleware still sets
        # Content-Length: 0 on them and uvicorn forwards it, so emit it too; only the
        # body bytes (and, for 304, Content-Type) are suppressed.
        cdef bint bodyless = self.status == 204 or self.status == 304
        cdef list parts = [b"HTTP/1.1 " + str(self.status).encode("ascii") + b" " + reason + b"\r\n"]
        if self.content_type or self.ct_present:
            parts.append(b"Content-Type: " + self.content_type + b"\r\n")
        parts.append(b"Content-Length: " + str(len(self.body)).encode("ascii") + b"\r\n")
        if not keep_alive:
            parts.append(b"Connection: close\r\n")
        cdef str key
        cdef bint has_date = False
        for key in self.headers:
            if key.lower() == "date":
                has_date = True
                break
        if not has_date:
            parts.append(b"Date: " + _http_date() + b"\r\n")
        cdef str name
        cdef object value
        for name, value in self.headers.items():
            parts.append(name.encode("latin1") + b": " + str(value).encode("latin1") + b"\r\n")
        cdef object cookie
        for cookie in self.cookies:
            parts.append(b"Set-Cookie: " + str(cookie).encode("latin1") + b"\r\n")
        parts.append(b"\r\n")
        if not is_head and not bodyless:
            parts.append(self.body)
        return b"".join(parts)


cpdef bytes response_to_bytes(Response resp, bint keep_alive):
    return resp.to_bytes(keep_alive)
