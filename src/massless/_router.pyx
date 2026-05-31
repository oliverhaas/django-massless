# src/massless/_router.pyx
# distutils: language = c++
from cython.operator cimport dereference as deref
from libcpp.string cimport string


cdef class Router:
    def __cinit__(self):
        self._dynamic = []

    def add_static(self, bytes path, int route_id):
        self._static[<string>path] = route_id

    def add_dynamic(self, bytes prefix, int route_id):
        # Matches `<prefix><int>`, e.g. prefix b"/items/" matches b"/items/123".
        self._dynamic.append((prefix, route_id))

    cdef MatchResult match_c(self, bytes path) except *:
        cdef MatchResult result
        result.route_id = -1
        result.param = -1
        cdef string key = <string>path
        cdef unordered_map[string, int].iterator it = self._static.find(key)
        if it != self._static.end():
            result.route_id = deref(it).second
            return result
        cdef bytes prefix
        cdef int rid
        cdef bytes tail
        for prefix, rid in self._dynamic:
            if path.startswith(prefix):
                tail = path[len(prefix):]
                if tail.isdigit():
                    result.route_id = rid
                    result.param = int(tail)
                    return result
        return result

    def match(self, bytes path):
        cdef MatchResult r = self.match_c(path)
        return (r.route_id, r.param)
