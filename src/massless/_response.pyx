import msgspec


cpdef tuple serialize_body(object obj):
    """Return (body_bytes, content_type_bytes) for a view return value."""
    if isinstance(obj, bytes):
        return obj, b"application/octet-stream"
    if isinstance(obj, str):
        return (<str>obj).encode("utf-8"), b"text/plain; charset=utf-8"
    return msgspec.json.encode(obj), b"application/json"
