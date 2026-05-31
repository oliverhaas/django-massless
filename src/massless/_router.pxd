# src/massless/_router.pxd
# distutils: language = c++
from libcpp.string cimport string
from libcpp.unordered_map cimport unordered_map


cdef struct MatchResult:
    int route_id
    long param


cdef class Router:
    cdef unordered_map[string, int] _static
    cdef list _dynamic
    cdef MatchResult match_c(self, bytes path) except *
