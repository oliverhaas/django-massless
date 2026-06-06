"""Load-test MASSLESS_POOL_LIFECYCLE against a real Postgres async pool.

Pool-lifecycle mode (django-bolt style) skips the request_started/request_finished signal
dispatch and instead returns the DB connection directly in the dispatch teardown
(``await aclose_old_connections()``). If that fails to return the connection to the pool, a
small pool exhausts: with max_size=2 and a short timeout, a 3rd concurrent borrow raises
PoolTimeout. So a flood of DB requests through the pool-lifecycle path succeeding on a
2-connection pool -- while the stats show requests actually queued for a connection -- proves
connections are returned per request. A negative control borrows max_size+1 connections without
returning to confirm the pool limit is genuinely enforced (so the positive run isn't trivial).

Requires the django-asyncio fork (AsyncConnectionPool + aclose_old_connections), psycopg with
the pool extra, and the postgres:17 container on 127.0.0.1:55432 (the fork's `django-asyncio-pg`):

    uv pip install "psycopg[binary,pool]"
    PYTHONPATH=/home/ohaas/e1+/django-asyncio \\
        .venv/bin/python benchmarks/pool_lifecycle_pg.py

Exits non-zero (assertion) on a leak/exhaustion; prints "RESULT: PASS" otherwise.
"""

import asyncio

import django
from django.conf import settings

MAX_SIZE = 2
TIMEOUT = 2

settings.configure(
    DEBUG=False,
    SECRET_KEY="x",  # noqa: S106
    ALLOWED_HOSTS=["*"],
    ROOT_URLCONF="__main__",
    MIDDLEWARE=[],
    INSTALLED_APPS=[],
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "djangoasync",
            "USER": "djangoasync",
            "PASSWORD": "djangoasync",
            "HOST": "127.0.0.1",
            "PORT": "55432",
            "CONN_MAX_AGE": 0,  # pooling requires non-persistent connections
            "CONN_HEALTH_CHECKS": False,
            "OPTIONS": {"pool": {"min_size": 1, "max_size": MAX_SIZE, "timeout": TIMEOUT}},
        },
    },
    MASSLESS_POOL_LIFECYCLE=True,
)
django.setup()

from django.db import connection, connections  # noqa: E402
from django.http import JsonResponse  # noqa: E402
from django.urls import path  # noqa: E402
from massless._protocol import dispatch, parse_request  # noqa: E402

from massless.handler import MasslessHandler  # noqa: E402


async def db_view(request):
    # A brief server-side sleep so concurrent requests genuinely saturate the small pool.
    async with await connection.acursor() as cur:
        await cur.execute("SELECT pg_sleep(0.02), 42")
        row = await cur.fetchone()
    return JsonResponse({"v": row[1]})


urlpatterns = [path("db", db_view)]

_RAW = b"GET /db HTTP/1.1\r\nHost: x\r\n\r\n"


async def _one(handler) -> bytes:
    raw, _ka = await dispatch(handler, parse_request(_RAW))
    return raw.split(b"\r\n", 1)[0]


async def _negative_control() -> bool:
    """Borrow max_size+1 connections without returning; the extra must PoolTimeout.

    Confirms the pool limit + timeout are real, so the positive run's all-success result
    actually demonstrates connection return rather than an unbounded pool.
    """
    pool = connections["default"].async_pool
    await pool.open(wait=True)
    held = [await pool.getconn() for _ in range(MAX_SIZE)]
    try:
        await pool.getconn(timeout=TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        timed_out = "timeout" in type(exc).__name__.lower() or "timeout" in str(exc).lower()
    else:
        timed_out = False
    for c in held:
        await pool.putconn(c)
    return timed_out


async def main() -> None:
    handler = MasslessHandler()
    assert handler._pool_lifecycle is True, "pool-lifecycle must be on"

    seq = 50
    for _ in range(seq):
        status = await _one(handler)
        assert b"200" in status, f"sequential request failed: {status!r}"
    print(f"sequential: {seq}/{seq} ok through pool-lifecycle teardown (max_size={MAX_SIZE})")

    burst = 30
    results = await asyncio.gather(*[asyncio.create_task(_one(handler)) for _ in range(burst)])
    cok = sum(1 for s in results if b"200" in s)
    assert cok == burst, f"pool exhausted under concurrency ({cok}/{burst}) -> connections leaked"
    print(f"concurrent: {cok}/{burst} ok ({MAX_SIZE}-connection pool cycled under {burst}-way load)")

    stats = connections["default"].async_pool.get_stats()
    print("pool stats:", {k: stats[k] for k in sorted(stats)})
    assert stats.get("requests_waiting", 0) == 0, "requests still queued -> leak/deadlock"
    assert stats["pool_size"] <= MAX_SIZE, "pool exceeded max_size"
    assert stats.get("requests_queued", 0) > 0, "no request ever queued -> pool wasn't the bottleneck (test too weak)"

    assert await _negative_control(), "negative control: pool did NOT time out -> limit not enforced"
    print(f"negative control: borrowing {MAX_SIZE + 1} from a max_size={MAX_SIZE} pool times out (limit enforced)")

    await connections["default"].aclose_pool()
    print("RESULT: PASS - MASSLESS_POOL_LIFECYCLE returns connections to the pool under load")


asyncio.run(main())
