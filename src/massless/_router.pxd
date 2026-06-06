cdef class Route:
    cdef list part_kind         # list[int] converter-kind code per part (0 = literal)
    cdef list part_lit          # list[bytes|None] literal bytes for literal parts
    cdef list part_name         # list[str|None] capture name for param parts
    cdef Py_ssize_t n_parts
    cdef object callback        # the view
    cdef bint is_async          # iscoroutinefunction(callback), computed once at build
    cdef dict default_args
    cdef str route_str
    cdef str name
    cdef object try_match(self, bytes path, Py_ssize_t off, Py_ssize_t plen)


cdef class Router:
    cdef list entries           # ordered: Route (fast) or None (opaque -> bail to Django)
    cpdef tuple match(self, bytes path)
