cdef class RequestCore:
    cdef bytes _method
    cdef bytes _path
    cdef bytes _query
    cdef list _headers          # list[tuple[bytes, bytes]], lower-cased names
    cdef bytes _body            # raw request body bytes (b"" when absent)
    cdef dict _query_cache       # parsed lazily

    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers, bytes body)
