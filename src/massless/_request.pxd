cdef class RequestCore:
    cdef bytes _method
    cdef bytes _path            # raw request-target path bytes (percent-encoded)
    cdef bytes _query
    cdef list _headers          # list[tuple[bytes, bytes]], lower-cased names
    cdef bytes _body            # raw request body bytes (b"" when absent)
    cdef dict _query_cache       # parsed lazily
    cdef tuple _client          # (host, port) of the TCP peer, or None
    cdef tuple _server          # (host, port) of the local bind address, or None

    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers, bytes body, tuple client=*, tuple server=*)
