"""Profile the Django pipeline massless runs per request, in-process, no sockets.

Builds a MasslessHandler and drives dispatch() for GET / many times under cProfile.
Everything below the C parse/serialize is Django's Python request pipeline: this
shows where the per-request microseconds actually go (resolver, middleware chain,
BaseHandler, request/response construction, signals).
"""

import asyncio
import cProfile
import io
import os
import pstats

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.settings")

import django

django.setup()

from massless._protocol import dispatch  # noqa: E402
from massless._request import RequestCore  # noqa: E402

from massless.handler import MasslessHandler  # noqa: E402

N = int(os.environ.get("N", "20000"))
HEADERS = [(b"host", b"127.0.0.1:8600"), (b"accept", b"*/*"), (b"user-agent", b"bench")]


def _core():
    return RequestCore.py_create(b"GET", b"/", b"", HEADERS, b"")


async def _run(n):
    handler = MasslessHandler()
    # warm up (first request resolves URLConf, builds middleware-bound view, etc.)
    await dispatch(handler, _core(), True)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(n):
        await dispatch(handler, _core(), True)
    pr.disable()
    return pr


def main():
    pr = asyncio.run(_run(N))
    st = pstats.Stats(pr)
    total = st.total_tt
    print(f"django version: {django.get_version()}")
    print(f"requests: {N}   total: {total:.3f}s   per-request: {total / N * 1e6:.1f} us")
    print("\n== top by cumulative time ==")
    buf = io.StringIO()
    st.stream = buf
    st.sort_stats("cumulative").print_stats(28)
    print(buf.getvalue())
    print("== top by internal (tottime) ==")
    buf2 = io.StringIO()
    st.stream = buf2
    st.sort_stats("tottime").print_stats(20)
    print(buf2.getvalue())


if __name__ == "__main__":
    main()
