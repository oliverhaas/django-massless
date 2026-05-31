cpdef tuple serialize_body(object obj)
cpdef bytes build_http_response(int status, bytes content_type, bytes body, bint keep_alive)
cpdef bytes reason_phrase(int status)


cdef class Response:
    cdef public int status
    cdef public dict headers
    cdef public list cookies
    cdef public bytes body
    cdef public bytes content_type

    cpdef bytes to_bytes(self, bint keep_alive)


cpdef bytes response_to_bytes(Response resp, bint keep_alive)
