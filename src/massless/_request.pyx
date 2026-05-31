from urllib.parse import parse_qs

from django.http import HttpRequest


cdef class RequestCore:
    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers):
        cdef RequestCore c = RequestCore.__new__(RequestCore)
        c._method = method
        c._path = path
        c._query = query
        c._headers = [(name.lower(), value) for name, value in headers]
        c._query_cache = None
        return c

    @staticmethod
    def py_create(bytes method, bytes path, bytes query, list headers):
        # Python-callable wrapper for tests.
        return RequestCore.create(method, path, query, headers)

    @property
    def method(self):
        return self._method.decode("ascii")

    @property
    def path(self):
        return self._path.decode("latin1")

    def get_header(self, str name):
        cdef bytes target = name.lower().encode("latin1")
        cdef bytes hname
        cdef bytes hvalue
        for hname, hvalue in self._headers:
            if hname == target:
                return hvalue.decode("latin1")
        return None

    def query_param(self, str name):
        if self._query_cache is None:
            self._query_cache = parse_qs(self._query.decode("latin1"))
        values = self._query_cache.get(name)
        return values[0] if values else None


class MasslessRequest(HttpRequest):
    """Regular HttpRequest subclass backed by a RequestCore. No HttpRequest.__init__
    call, so Django-machinery attrs are absent until promotion (Phase 2)."""

    def __init__(self, core, path_params):
        self._core = core
        self.path_params = path_params

    method = property(lambda self: self._core.method)
    path = property(lambda self: self._core.path)

    def get_header(self, name):
        return self._core.get_header(name)

    def query_param(self, name):
        return self._core.query_param(name)
