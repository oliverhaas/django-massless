import io
from urllib.parse import parse_qs

from django.http import HttpRequest
from django.core.handlers.wsgi import WSGIRequest


cdef class RequestCore:
    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers, bytes body):
        cdef RequestCore c = RequestCore.__new__(RequestCore)
        c._method = method
        c._path = path
        c._query = query
        c._headers = [(name.lower(), value) for name, value in headers]
        c._body = body if body is not None else b""
        c._query_cache = None
        return c

    @staticmethod
    def py_create(bytes method, bytes path, bytes query, list headers, bytes body=b""):
        # Python-callable wrapper for tests.
        return RequestCore.create(method, path, query, headers, body)

    @property
    def method(self):
        return self._method.decode("ascii")

    @property
    def path(self):
        return self._path.decode("latin1")

    @property
    def body(self):
        return self._body

    def headers_list(self):
        # list[tuple[bytes, bytes]] with lower-cased header names.
        return self._headers

    def query_string(self):
        # Raw query bytes decoded latin1 (WSGI QUERY_STRING is a native str).
        return self._query.decode("latin1")

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


class MasslessRequest(WSGIRequest):
    """A WSGIRequest subclass backed by a RequestCore. No WSGIRequest.__init__
    call at construction, so Django-machinery attrs are absent until promotion.
    The fast path serves method/path/get_header/query_param from the core; the
    first access to any Django-machinery attribute promotes the object once by
    reconstructing it through WSGIRequest.__init__ from a WSGI environ built from
    the core buffers."""

    def __init__(self, core, path_params):
        self._core = core
        self.path_params = path_params
        self.method = core.method
        self.path = core.path
        self._is_django = False

    def get_header(self, name):
        return self._core.get_header(name)

    def query_param(self, name):
        return self._core.query_param(name)

    # --- promotion ---
    def _build_wsgi_environ(self):
        core = self._core
        body = core.body
        headers = core.headers_list()  # list[tuple[bytes, bytes]] lower-cased
        host = b""
        environ = {
            "REQUEST_METHOD": self.method,
            "PATH_INFO": self.path,
            "QUERY_STRING": core.query_string(),
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.input": io.BytesIO(body),
            "wsgi.url_scheme": "http",
            "CONTENT_LENGTH": str(len(body)),
        }
        for name, value in headers:
            n = name.decode("latin1")
            v = value.decode("latin1")
            if n == "content-type":
                environ["CONTENT_TYPE"] = v
            elif n == "content-length":
                pass  # CONTENT_LENGTH is derived from the actual body length, not the client header
            else:
                environ["HTTP_" + n.upper().replace("-", "_")] = v
            if n == "host":
                host = value
        server_name, _, server_port = host.decode("latin1").partition(":")
        environ["SERVER_NAME"] = server_name or "localhost"
        environ["SERVER_PORT"] = server_port or "80"
        return environ

    def _ensure_promoted(self):
        if not self._is_django:
            self._promote()

    def _promote(self):
        # Latch first so any property setters fired inside WSGIRequest.__init__
        # (e.g. self.encoding = charset in _set_content_type_params) delegate to
        # the HttpRequest implementation instead of re-entering _promote.
        self._is_django = True
        WSGIRequest.__init__(self, self._build_wsgi_environ())

    def __getattr__(self, name):
        # Called only on a normal-lookup miss.
        if name.startswith("_") or self.__dict__.get("_is_django"):
            raise AttributeError(name)
        self._promote()
        return object.__getattribute__(self, name)

    # --- bounded overrides for property/method attrs that bypass __getattr__ ---
    @property
    def body(self):
        self._ensure_promoted()
        return HttpRequest.body.fget(self)

    @property
    def encoding(self):
        self._ensure_promoted()
        return HttpRequest.encoding.fget(self)

    @encoding.setter
    def encoding(self, value):
        self._ensure_promoted()
        HttpRequest.encoding.fset(self, value)

    @property
    def headers(self):
        self._ensure_promoted()
        return HttpRequest.__dict__["headers"].func(self)

    # GET/COOKIES are WSGIRequest cached_propertys; POST/FILES are propertys.
    # All four are class descriptors, so they shadow __getattr__ and would run
    # against an unset environ before promotion. Promote first, then delegate.
    #
    # POST/FILES read self._post/_files, which _load_post_and_files() sets once,
    # so their fget is naturally identity-stable. GET/COOKIES are cached_propertys
    # whose .func() recomputes a fresh QueryDict per call; since this property is a
    # data descriptor it shadows the instance __dict__ cache cached_property relies
    # on, so we cache the computed value in a private slot to keep Django's identity
    # semantics (req.GET is req.GET).
    @property
    def GET(self):
        self._ensure_promoted()
        cached = self.__dict__.get("_get_cache")
        if cached is None:
            cached = WSGIRequest.__dict__["GET"].func(self)
            self.__dict__["_get_cache"] = cached
        return cached

    @GET.deleter
    def GET(self):
        # Django's encoding setter does `del self.GET` to force a re-decode. Our GET
        # override is a data-descriptor property (no instance-dict entry to delete),
        # so drop our private cache instead; the next access recomputes with the new
        # encoding. Without this deleter, `self.encoding = charset` (fired inside
        # WSGIRequest.__init__ for any Content-Type with a charset param) raises and
        # aborts promotion.
        self.__dict__.pop("_get_cache", None)

    @property
    def POST(self):
        self._ensure_promoted()
        return WSGIRequest.__dict__["POST"].fget(self)

    @property
    def COOKIES(self):
        self._ensure_promoted()
        cached = self.__dict__.get("_cookies_cache")
        if cached is None:
            cached = WSGIRequest.__dict__["COOKIES"].func(self)
            self.__dict__["_cookies_cache"] = cached
        return cached

    @COOKIES.deleter
    def COOKIES(self):
        # Defensive symmetry with GET: drop our private cache so any `del self.COOKIES`
        # cannot raise on the data-descriptor property.
        self.__dict__.pop("_cookies_cache", None)

    @property
    def FILES(self):
        self._ensure_promoted()
        return WSGIRequest.__dict__["FILES"].fget(self)

    @property
    def scheme(self):
        self._ensure_promoted()
        return HttpRequest.scheme.fget(self)

    def get_host(self):
        self._ensure_promoted()
        return HttpRequest.get_host(self)

    def get_port(self):
        self._ensure_promoted()
        return HttpRequest.get_port(self)

    def is_secure(self):
        self._ensure_promoted()
        return HttpRequest.is_secure(self)

    def build_absolute_uri(self, location=None):
        self._ensure_promoted()
        return HttpRequest.build_absolute_uri(self, location)

    def read(self, *a, **k):
        self._ensure_promoted()
        return HttpRequest.read(self, *a, **k)

    def readline(self, *a, **k):
        self._ensure_promoted()
        return HttpRequest.readline(self, *a, **k)

    def __iter__(self):
        self._ensure_promoted()
        return HttpRequest.__iter__(self)

    def close(self):
        # Closing an un-promoted request is a no-op: there are no upload handlers or
        # streams to release until promotion, so don't force promotion just to close.
        if self._is_django:
            HttpRequest.close(self)
