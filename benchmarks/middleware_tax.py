"""Quantify the middleware tax massless's native-async chain removes, in-process, single-core.

Stock Django's built-in middleware are ``MiddlewareMixin`` classes: under ASGI every ``process_*``
hook runs through ``sync_to_async(thread_sensitive=True)`` -- a thread-pool round-trip per hook,
per request. massless's owned chain substitutes a same-named native-async re-implementation for
each common built-in (see massless._middleware), running the identical hook logic in the event
loop with no thread hop (the one hook with backend I/O, the session save, awaits the backend's
async API instead of blocking). ``MASSLESS_FAST_MIDDLEWARE`` toggles the substitution.

This script drives ``dispatch()`` through the chain for an incrementally larger stack and measures
wall-clock per-request cost, so each middleware's marginal contribution is isolated, and contrasts
the full production stack with substitution ON (native-async) vs OFF (the stock thread-hopping
classes). It also times a bare ``sync_to_async(thread_sensitive=True)`` round-trip so the recovered
cost can be attributed to the thread hop rather than to the middleware's intrinsic work.

Single-core, no sockets. Pin it:

    taskset -c 0 .venv/bin/python benchmarks/middleware_tax.py
    # against the fork (its built-ins are already native-async, so ON==OFF):
    taskset -c 0 env PYTHONPATH=/home/ohaas/e1+/django-asyncio .venv/bin/python benchmarks/middleware_tax.py
"""

import asyncio
import os
from time import perf_counter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.settings")
os.environ.setdefault("BENCH_FULL_MIDDLEWARE", "1")  # installs auth/sessions/messages apps

import django

django.setup()

from asgiref.sync import sync_to_async  # noqa: E402
from django.conf import settings  # noqa: E402
from massless._protocol import dispatch  # noqa: E402
from massless._request import RequestCore  # noqa: E402

from massless.handler import MasslessHandler  # noqa: E402

N = int(os.environ.get("N", "20000"))
REPEATS = int(os.environ.get("REPEATS", "3"))
HEADERS = [(b"host", b"127.0.0.1:8600"), (b"accept", b"*/*"), (b"user-agent", b"bench")]

SECURITY = "django.middleware.security.SecurityMiddleware"
SESSION = "django.contrib.sessions.middleware.SessionMiddleware"
COMMON = "django.middleware.common.CommonMiddleware"
CSRF = "django.middleware.csrf.CsrfViewMiddleware"
AUTH = "django.contrib.auth.middleware.AuthenticationMiddleware"
MESSAGES = "django.contrib.messages.middleware.MessageMiddleware"
XFRAME = "django.middleware.clickjacking.XFrameOptionsMiddleware"

FULL = [SECURITY, SESSION, COMMON, CSRF, AUTH, MESSAGES, XFRAME]

# The build grows the canonical 7-middleware stack one entry at a time (Session before Auth, as
# Auth reads request.session), all with substitution ON, so each row's delta is that middleware's
# native-async marginal cost. The header-only trio (Security/Common/XFrame) is also shown stock,
# and the full stack is shown both ways, to size the substitution win.
STACKS = [
    ("floor: no middleware (fast path)", [], True),
    ("Security+Common+XFrame (native-async)", [SECURITY, COMMON, XFRAME], True),
    ("Security+Common+XFrame (stock)", [SECURITY, COMMON, XFRAME], False),
    ("  + Session   (native-async)", [SECURITY, SESSION, COMMON, XFRAME], True),
    ("  + CSRF      (native-async)", [SECURITY, SESSION, COMMON, CSRF, XFRAME], True),
    ("  + Auth      (native-async)", [SECURITY, SESSION, COMMON, CSRF, AUTH, XFRAME], True),
    ("  + Messages  (native-async) = FULL", FULL, True),
    ("FULL stack (all stock, substitution OFF)", FULL, False),
]
_NATIVE3 = "Security+Common+XFrame (native-async)"
_FULL_NATIVE = "  + Messages  (native-async) = FULL"
_FULL_STOCK = "FULL stack (all stock, substitution OFF)"

# Thread hops the 4 stateful middleware pay when stock: MiddlewareMixin.__acall__ runs
# process_request + process_response (2 hops); the chain runs process_view separately (1 more).
# Session req+resp=2; CSRF req+view+resp=3; Auth req only=1; Messages req+resp=2. Total = 8.
STATEFUL_HOOKS = 8


def _core() -> RequestCore:
    return RequestCore.py_create(b"GET", b"/", b"", HEADERS, b"")


async def _bench(mw_list: list[str], *, fast_on: bool) -> float:
    """Best-of-REPEATS per-request microseconds for this stack, driven through the chain."""
    settings.MIDDLEWARE = list(mw_list)
    settings.MASSLESS_FAST_MIDDLEWARE = fast_on
    handler = MasslessHandler()

    raw, _ka = await dispatch(handler, _core(), True)  # warm + correctness
    status = raw.split(b"\r\n", 1)[0]
    assert b"200" in status, f"stack {mw_list} did not return 200: {status!r}"

    best = float("inf")
    for _ in range(REPEATS):
        t0 = perf_counter()
        for _ in range(N):
            await dispatch(handler, _core(), True)
        best = min(best, perf_counter() - t0)
    return best / N * 1e6


async def _threadhop_us() -> float:
    """Cost of one sync_to_async(thread_sensitive=True) round-trip in this event loop."""
    hop = sync_to_async(lambda: None, thread_sensitive=True)
    await hop()  # warm the thread pool
    best = float("inf")
    for _ in range(REPEATS):
        t0 = perf_counter()
        for _ in range(N):
            await hop()
        best = min(best, perf_counter() - t0)
    return best / N * 1e6


async def main() -> None:
    print(f"django {django.get_version()}   N={N}   repeats={REPEATS}   (best-of)\n")
    print(f"{'stack':<44}{'us/req':>9}{'rps':>10}{'delta us':>10}")
    print("-" * 73)
    rows = []
    prev = None
    for label, mw, fast_on in STACKS:
        us = await _bench(mw, fast_on=fast_on)
        delta = (
            "" if prev is None or label.startswith(("FULL", "Security+Common+XFrame (stock")) else f"{us - prev:+.1f}"
        )
        print(f"{label:<44}{us:>9.1f}{1e6 / us:>10.0f}{delta:>10}")
        rows.append((label, us))
        if label.strip().startswith("+") or label == _NATIVE3:
            prev = us

    by = dict(rows)
    full_native = by[_FULL_NATIVE]
    full_stock = by[_FULL_STOCK]
    native3 = by[_NATIVE3]
    win = full_stock - full_native
    hop = await _threadhop_us()

    print("\n-- the substitution win " + "-" * 49)
    print(f"FULL stack native-async: {full_native:7.1f} us/req ({1e6 / full_native:5.0f} rps)")
    print(f"FULL stack all-stock:    {full_stock:7.1f} us/req ({1e6 / full_stock:5.0f} rps)")
    print(f"=> substituting the chain removes {win:.1f} us/req: {full_stock / full_native:.2f}x on the full stack")
    print(
        f"\nbare thread-hop round-trip: {hop:.1f} us  ->  {STATEFUL_HOOKS} stateful hops ~= {STATEFUL_HOOKS * hop:.1f} us",
    )
    print(f"4 stateful middleware, native-async, add only {full_native - native3:.1f} us/req over the header trio")
    print("(that residual is intrinsic work -- crypto/cookies -- the thread hop is gone)")


if __name__ == "__main__":
    asyncio.run(main())
