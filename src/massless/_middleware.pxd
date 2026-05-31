from massless._response cimport Response


cdef class Middleware:
    cpdef object before(self, object req)
    cpdef object after(self, object req, Response resp)


cpdef object run_before(list chain, object req)
cpdef void run_after(list chain, object req, Response resp)
