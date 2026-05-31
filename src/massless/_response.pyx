import msgspec


cpdef tuple serialize_body(object obj):
    """Return (body_bytes, content_type_bytes) for a view return value."""
    if isinstance(obj, bytes):
        return obj, b"application/octet-stream"
    if isinstance(obj, str):
        return (<str>obj).encode("utf-8"), b"text/plain; charset=utf-8"
    return msgspec.json.encode(obj), b"application/json"


cdef dict _REASON = {200: b"OK", 404: b"Not Found", 422: b"Unprocessable Entity", 500: b"Internal Server Error"}


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
