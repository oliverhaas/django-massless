# cython: language_level=3str
"""A typed Cython router that resolves the common ``path()`` URLconf in C.

It is built from Django's own ``urlpatterns`` (so the app's ``urls.py`` is the only
routing source -- no decorators, fully drop-in) and matches a request path against a
precompiled, regex-free table: literal segments are compared as bytes and converter
parameters (``int``/``str``/``slug``/``uuid``/``path``) are consumed by charset.

Correctness is by construction. Anything the table cannot represent exactly -- a
``re_path``, a custom/registered converter, an include prefix it cannot parse, or a
greedy boundary that regex backtracking would resolve differently -- is recorded as an
opaque marker. ``match()`` walks entries in URLconf order; reaching an opaque marker (or
finding no match) returns ``None``, and the caller falls back to Django's resolver. A
non-None result is therefore always identical to what Django would have resolved.
"""

import uuid as _uuid_mod

from asgiref.sync import iscoroutinefunction
from django.conf import settings
from django.urls import get_resolver
from django.urls.resolvers import (
    URLPattern,
    URLResolver,
    RoutePattern,
    _PATH_PARAMETER_COMPONENT_RE,
)


cdef enum:
    K_LIT = 0    # literal bytes
    K_INT = 1    # [0-9]+        -> int
    K_STR = 2    # [^/]+         -> str
    K_SLUG = 3   # [-a-zA-Z0-9_]+ -> str
    K_UUID = 4   # 8-4-4-4-12 lowercase hex -> uuid.UUID
    K_PATH = 5   # .+ (greedy, last part only) -> str


_KIND = {"int": K_INT, "str": K_STR, "slug": K_SLUG, "uuid": K_UUID, "path": K_PATH}


cdef inline bint _is_slug(unsigned char c) noexcept nogil:
    return (
        (48 <= c <= 57)      # 0-9
        or (65 <= c <= 90)   # A-Z
        or (97 <= c <= 122)  # a-z
        or c == 45           # -
        or c == 95           # _
    )


cdef inline bint _is_lower_hex(unsigned char c) noexcept nogil:
    return (48 <= c <= 57) or (97 <= c <= 102)  # 0-9 a-f


cdef inline bint _match_uuid(const unsigned char[::1] b, Py_ssize_t s, Py_ssize_t plen) noexcept nogil:
    # Exactly 36 chars: 8 hex '-' 4 hex '-' 4 hex '-' 4 hex '-' 12 hex (lowercase).
    cdef Py_ssize_t i
    cdef unsigned char c
    if s + 36 > plen:
        return False
    for i in range(36):
        c = b[s + i]
        if i == 8 or i == 13 or i == 18 or i == 23:
            if c != 45:  # '-'
                return False
        elif not _is_lower_hex(c):
            return False
    return True


cdef class Route:
    cdef object try_match(self, bytes path, Py_ssize_t off, Py_ssize_t plen):
        """Match this route against ``path[off:plen]`` (the path after the leading '/').

        Returns the captured kwargs dict (possibly empty) on a full match, else None.
        """
        cdef const unsigned char[::1] buf = path
        cdef Py_ssize_t cur = off
        cdef Py_ssize_t i, start
        cdef int kind
        cdef bytes lit
        cdef bytes val
        cdef str name
        cdef dict kwargs = {}
        for i in range(self.n_parts):
            kind = <int>self.part_kind[i]
            if kind == K_LIT:
                lit = <bytes>self.part_lit[i]
                if not path.startswith(lit, cur):
                    return None
                cur += len(lit)
            else:
                start = cur
                if kind == K_INT:
                    while cur < plen and 48 <= buf[cur] <= 57:
                        cur += 1
                elif kind == K_STR:
                    while cur < plen and buf[cur] != 47:  # not '/'
                        cur += 1
                elif kind == K_SLUG:
                    while cur < plen and _is_slug(buf[cur]):
                        cur += 1
                elif kind == K_PATH:
                    cur = plen
                elif kind == K_UUID:
                    if not _match_uuid(buf, cur, plen):
                        return None
                    cur += 36
                if cur == start:  # converters require at least one character
                    return None
                val = path[start:cur]
                name = <str>self.part_name[i]
                try:
                    if kind == K_INT:
                        kwargs[name] = int(val)
                    elif kind == K_UUID:
                        kwargs[name] = _uuid_mod.UUID(val.decode("ascii"))
                    else:
                        kwargs[name] = val.decode("utf-8")
                except Exception:
                    return None
        if cur != plen:
            return None
        if self.default_args:
            kwargs.update(self.default_args)
        return kwargs


cdef class Router:
    cpdef tuple match(self, bytes path):
        """Return (callback, args, kwargs, route_str) for a fast match, else None.

        None means "defer to Django's resolver" -- either an opaque entry was reached in
        URLconf order or nothing matched. A non-None result equals Django's resolution.
        """
        cdef Py_ssize_t plen = len(path)
        if plen == 0 or path[0] != 47:  # must start with '/'
            return None
        cdef Route r
        cdef object kw
        for entry in self.entries:
            if entry is None:
                return None  # opaque pattern has priority here; let Django resolve
            r = <Route>entry
            kw = r.try_match(path, 1, plen)  # skip the leading '/'
            if kw is not None:
                return (r.callback, (), kw, r.route_str, r.is_async)
        return None

    def stats(self):
        """(fast_routes, opaque_markers) -- for diagnostics/tests."""
        cdef int fast = 0, opaque = 0
        for entry in self.entries:
            if entry is None:
                opaque += 1
            else:
                fast += 1
        return fast, opaque


def _parse_raw(str route):
    """Split a route string into raw parts, or None for an unknown converter.

    Each part is (kind, literal_bytes|None, name|None). Empty literals are dropped.
    """
    cdef list parts = []
    cdef Py_ssize_t prev = 0
    for m in _PATH_PARAMETER_COMPONENT_RE.finditer(route):
        raw_conv = m.group("converter")
        if raw_conv is None:
            raw_conv = "str"
        kind = _KIND.get(raw_conv)
        if kind is None:
            return None  # custom/registered converter -> cannot fast-match
        start, end = m.span()
        lit = route[prev:start]
        if lit:
            parts.append((K_LIT, lit.encode("utf-8"), None))
        parts.append((kind, None, m.group("parameter")))
        prev = end
    tail = route[prev:]
    if tail:
        parts.append((K_LIT, tail.encode("utf-8"), None))
    return parts


def _finalize(list parts):
    """Merge adjacent literals and verify greedy matching equals regex; None if not.

    A param is safe only when it is the last part, or is followed by a literal whose
    first byte the param's charset cannot consume (so the greedy scan stops exactly
    where the literal begins). 'path' (.+) must be the final part.
    """
    cdef list merged = []
    for p in parts:
        if p[0] == K_LIT and merged and merged[-1][0] == K_LIT:
            merged[-1] = (K_LIT, merged[-1][1] + p[1], None)
        else:
            merged.append(p)
    cdef Py_ssize_t n = len(merged)
    cdef Py_ssize_t i
    cdef int c
    for i in range(n):
        kind = merged[i][0]
        if kind == K_LIT:
            continue
        if kind == K_PATH and i != n - 1:
            return None
        if i == n - 1:
            continue  # trailing param consumes to end == regex \Z
        nxt = merged[i + 1]
        if nxt[0] != K_LIT:
            return None  # param immediately followed by another param: ambiguous
        c = nxt[1][0]  # first byte of the following literal
        if kind == K_INT:
            if 48 <= c <= 57:
                return None
        elif kind == K_STR:
            if c != 47:  # [^/]+ only stops at '/'
                return None
        elif kind == K_SLUG:
            if _is_slug(<unsigned char>c):
                return None
        # K_UUID consumes a fixed 36 chars, so any following literal is safe.
    return merged


cdef Route _make_route(list parts, object callback, dict default_args, str route_str, str name):
    cdef Route r = Route.__new__(Route)
    r.part_kind = [p[0] for p in parts]
    r.part_lit = [p[1] for p in parts]
    r.part_name = [p[2] for p in parts]
    r.n_parts = len(parts)
    r.callback = callback
    r.is_async = iscoroutinefunction(callback)
    r.default_args = default_args or {}
    r.route_str = route_str
    r.name = name
    return r


def _walk(patterns, list prefix_parts, str route_prefix, list entries):
    for p in patterns:
        if isinstance(p, URLPattern):
            pat = p.pattern
            if isinstance(pat, RoutePattern):
                raw = _parse_raw(str(pat._route))
                if raw is None:
                    entries.append(None)
                    continue
                final = _finalize(prefix_parts + raw)
                if final is None:
                    entries.append(None)
                    continue
                entries.append(
                    _make_route(final, p.callback, p.default_args, route_prefix + str(pat._route), p.name),
                )
            else:
                entries.append(None)  # RegexPattern leaf
        elif isinstance(p, URLResolver):
            pat = p.pattern
            if isinstance(pat, RoutePattern):
                raw = _parse_raw(str(pat._route))
                if raw is None:
                    entries.append(None)
                    continue
                _walk(p.url_patterns, prefix_parts + raw, route_prefix + str(pat._route), entries)
            else:
                entries.append(None)  # regex include prefix
        else:
            entries.append(None)


def build_router(urlconf=None):
    """Build a Router from ``urlconf`` (defaults to settings.ROOT_URLCONF)."""
    name = urlconf if urlconf is not None else settings.ROOT_URLCONF
    resolver = get_resolver(name)
    cdef Router router = Router.__new__(Router)
    router.entries = []
    _walk(resolver.url_patterns, [], "", router.entries)
    return router
