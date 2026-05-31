import msgspec


cpdef tuple serialize_body(object obj):
    """Return (body_bytes, content_type_bytes) for a view return value."""
    if isinstance(obj, bytes):
        return obj, b"application/octet-stream"
    if isinstance(obj, str):
        return (<str>obj).encode("utf-8"), b"text/plain; charset=utf-8"
    return msgspec.json.encode(obj), b"application/json"


cdef dict _REASON = {
    200: b"OK",
    204: b"No Content",
    400: b"Bad Request",
    401: b"Unauthorized",
    403: b"Forbidden",
    404: b"Not Found",
    422: b"Unprocessable Entity",
    429: b"Too Many Requests",
    500: b"Internal Server Error",
}


cpdef bytes build_http_response(int status, bytes content_type, bytes body, bint keep_alive):
    cdef bytes reason = _REASON.get(status, b"OK")
    cdef bytes conn = b"keep-alive" if keep_alive else b"close"
    return (
        b"HTTP/1.1 " + str(status).encode("ascii") + b" " + reason + b"\r\n" +
        b"Content-Type: " + content_type + b"\r\n" +
        b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n" +
        b"Connection: " + conn + b"\r\n\r\n" +
        body
    )


cpdef bytes reason_phrase(int status):
    return _REASON.get(status, b"OK")


cdef class Response:
    """A lightweight response value for fast-tier middleware.

    Carries a status, an ordered header dict (name -> value, both str), and a
    bytes body. Used for middleware short-circuits (preflight 204, 401, 429) and
    as the wrapper a view return is folded into so ``after()`` hooks can mutate
    headers before the C serializer emits the wire bytes.

    Fields are declared in _response.pxd so other extensions can cimport them.
    """

    def __init__(self, int status, dict headers=None, bytes body=b"",
                 bytes content_type=b"application/octet-stream"):
        self.status = status
        self.headers = dict(headers) if headers is not None else {}
        # Set-Cookie cannot live in `headers` (a dict can't hold repeats); the
        # bridge appends each cookie's OutputString() here, emitted one line each.
        self.cookies = []
        self.body = body if body is not None else b""
        self.content_type = content_type

    @staticmethod
    def from_view_result(object obj):
        """Build a Response (200) from a view's dict/bytes/str return value."""
        cdef bytes body
        cdef bytes ctype
        body, ctype = serialize_body(obj)
        return Response(200, {}, body, ctype)

    cpdef bytes to_bytes(self, bint keep_alive):
        """Serialize to HTTP/1.1 wire bytes, appending any extra headers."""
        cdef bytes reason = _REASON.get(self.status, b"OK")
        cdef bytes conn = b"keep-alive" if keep_alive else b"close"
        cdef list parts = [
            b"HTTP/1.1 " + str(self.status).encode("ascii") + b" " + reason + b"\r\n",
            b"Content-Type: " + self.content_type + b"\r\n",
            b"Content-Length: " + str(len(self.body)).encode("ascii") + b"\r\n",
            b"Connection: " + conn + b"\r\n",
        ]
        cdef str name
        cdef object value
        for name, value in self.headers.items():
            parts.append(name.encode("latin1") + b": " + str(value).encode("latin1") + b"\r\n")
        cdef object cookie
        for cookie in self.cookies:
            parts.append(b"Set-Cookie: " + str(cookie).encode("latin1") + b"\r\n")
        parts.append(b"\r\n")
        parts.append(self.body)
        return b"".join(parts)


cpdef bytes response_to_bytes(Response resp, bint keep_alive):
    return resp.to_bytes(keep_alive)
