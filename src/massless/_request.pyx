import io
from urllib.parse import parse_qs, unquote, unquote_to_bytes

from django.http import HttpRequest
from django.core.handlers.wsgi import WSGIRequest

from massless._proxy import forwarded_overrides


cdef class RequestCore:
    @staticmethod
    cdef RequestCore create(bytes method, bytes path, bytes query, list headers, bytes body, tuple client=None, tuple server=None):
        cdef RequestCore c = RequestCore.__new__(RequestCore)
        c._method = method
        c._path = path
        c._query = query
        c._headers = [(name.lower(), value) for name, value in headers]
        c._body = body if body is not None else b""
        c._query_cache = None
        c._client = client
        c._server = server
        return c

    @staticmethod
    def py_create(bytes method, bytes path, bytes query, list headers, bytes body=b"", tuple client=None, tuple server=None):
        # Python-callable wrapper for tests.
        return RequestCore.create(method, path, query, headers, body, client, server)

    @property
    def method(self):
        return self._method.decode("ascii")

    @property
    def path(self):
        # Percent-decoded Unicode path, matching the ASGI scope["path"] uvicorn hands
        # Django (so the URL resolver sees the same value). The raw path is ASCII; a
        # latin1 decode never fails, and unquote then decodes the escapes as UTF-8.
        cdef str raw = self._path.decode("latin1")
        return unquote(raw) if "%" in raw else raw

    @property
    def wsgi_path(self):
        # PATH_INFO for the promoted WSGIRequest. Django's get_path_info re-encodes
        # this latin1 and decodes UTF-8, so it must be the percent-decoded bytes read
        # as latin1 (the WSGI convention), not the clean Unicode str.
        cdef str raw = self._path.decode("latin1")
        if "%" not in raw:
            return raw
        return unquote_to_bytes(raw).decode("latin1")

    @property
    def client(self):
        return self._client

    @property
    def server(self):
        return self._server

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
        # Django's URL resolver reads request.path_info first; expose it as a plain
        # attr so resolution does not trigger promotion (it is just the path).
        self.path_info = core.path
        self._is_django = False
        # Fast-tier auth claims, set as a plain instance attribute. Present from
        # construction so reading/writing request.auth never triggers __getattr__
        # promotion. JWTAuth sets this to the decoded claims dict.
        self.auth = None
        self._user = None

    def get_header(self, name):
        return self._core.get_header(name)

    def query_param(self, name):
        return self._core.query_param(name)

    # --- lazy DB-backed user (promote + ORM) ---
    def _resolve_user_model(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import AnonymousUser

        auth = self.auth
        sub = auth.get("sub") if auth else None
        if sub is None:
            return AnonymousUser(), None
        return None, sub

    @property
    def user(self):
        """The DB-backed user. Accessing this promotes the request and resolves
        the user from request.auth's ``sub`` claim via the user model (sync ORM).
        Caches on self._user. AnonymousUser when there is no auth/sub."""
        if self._user is not None:
            return self._user
        # Promote: a DB-backed user is a Django concern.
        self._ensure_promoted()
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import AnonymousUser

        user_model = get_user_model()
        resolved, sub = self._resolve_user_model()
        if resolved is not None:
            self._user = resolved
            return self._user
        try:
            self._user = user_model.objects.get(pk=sub)
        except user_model.DoesNotExist:
            # Legitimate "no such user" -> AnonymousUser. Anything else (e.g.
            # SynchronousOnlyOperation when called under the running loop) must
            # propagate so the misuse surfaces instead of silently downgrading.
            self._user = AnonymousUser()
        return self._user

    @user.setter
    def user(self, value):
        # Django's AuthenticationMiddleware (bridge tier) assigns request.user;
        # honor it so the property doesn't shadow a Django-set user.
        self._user = value

    async def aget_user(self):
        """Async variant of ``user`` for async views: promote + async ORM get."""
        if self._user is not None:
            return self._user
        self._ensure_promoted()
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import AnonymousUser

        user_model = get_user_model()
        resolved, sub = self._resolve_user_model()
        if resolved is not None:
            self._user = resolved
            return self._user
        try:
            self._user = await user_model.objects.aget(pk=sub)
        except user_model.DoesNotExist:
            self._user = AnonymousUser()
        return self._user

    # --- promotion ---
    def _build_wsgi_environ(self):
        core = self._core
        body = core.body
        headers = core.headers_list()  # list[tuple[bytes, bytes]] lower-cased
        environ = {
            "REQUEST_METHOD": self.method,
            "PATH_INFO": core.wsgi_path,
            "QUERY_STRING": core.query_string(),
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.input": io.BytesIO(body),
            "wsgi.url_scheme": "http",
            "CONTENT_LENGTH": str(len(body)),
        }
        # Fold headers into META the way Django's ASGIRequest does (asgi.py): drop names
        # containing "_" (the underscore/hyphen spoofing guard), join repeats of the same
        # header with "," and Cookie with "; ". CONTENT_LENGTH stays derived from the
        # actual body length, not the client-sent header.
        collected = {}  # HTTP_* / CONTENT_TYPE name -> list[str]
        for name, value in headers:
            n = name.decode("latin1")
            if "_" in n:
                continue
            v = value.decode("latin1")
            if n == "content-type":
                key = "CONTENT_TYPE"
            elif n == "content-length":
                continue
            else:
                key = "HTTP_" + n.upper().replace("-", "_")
            if key == "HTTP_COOKIE":
                v = v.rstrip("; ")
            collected.setdefault(key, []).append(v)
        cookies = collected.pop("HTTP_COOKIE", None)
        if cookies is not None:
            environ["HTTP_COOKIE"] = "; ".join(cookies)
        for key, values in collected.items():
            environ[key] = ",".join(values)
        # SERVER_NAME/SERVER_PORT come from the local bind address (Django's
        # scope["server"]), not the Host header (which is HTTP_HOST / get_host()).
        server = core.server
        if server is not None:
            environ["SERVER_NAME"] = str(server[0])
            environ["SERVER_PORT"] = str(server[1])
        else:
            environ["SERVER_NAME"] = "unknown"
            environ["SERVER_PORT"] = "0"
        # Client address + scheme. Like Django (REMOTE_ADDR from scope["client"]) and
        # uvicorn's default proxy-header handling: honor a single X-Forwarded-Proto /
        # X-Forwarded-For only from a trusted peer; otherwise use the direct peer.
        client = core.client
        if client is not None:
            remote_host, remote_port = client[0], client[1]
            scheme, forwarded_client = forwarded_overrides(remote_host, headers)
            if scheme is not None:
                environ["wsgi.url_scheme"] = scheme
            if forwarded_client is not None:
                remote_host, remote_port = forwarded_client
            environ["REMOTE_ADDR"] = str(remote_host)
            environ["REMOTE_HOST"] = str(remote_host)
            environ["REMOTE_PORT"] = str(remote_port)
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
