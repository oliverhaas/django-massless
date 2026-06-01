cpdef tuple serialize_body(object obj)
cpdef bytes build_http_response(int status, bytes content_type, bytes body, bint keep_alive, bytes method=*)
cpdef bytes reason_phrase(int status)


cdef class Response:
    cdef public int status
    cdef public dict headers
    cdef public list cookies
    cdef public bytes body
    cdef public bytes content_type
    cdef public bytes reason     # exact reason phrase from Django; falls back to the table when empty
    cdef public bint ct_present  # True if the source response carried a Content-Type (even empty)

    cpdef bytes to_bytes(self, bint keep_alive, bytes method=*)


cpdef bytes response_to_bytes(Response resp, bint keep_alive)
