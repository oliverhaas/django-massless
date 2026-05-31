"""Task 2/3: sync views run on the thread-pool executor (off the loop thread),
async views run on the loop, and unhandled view errors log + return a 500."""

import asyncio
import logging
import threading

import pytest
from django.test import override_settings
from massless._protocol import dispatch, parse_request

from massless.app import MasslessAPI


def _dispatch(api, path):
    router = api.build_router()
    core = parse_request(b"GET " + path.encode() + b" HTTP/1.1\r\nHost: x\r\n\r\n")
    route_id, param = router.match(path.encode())
    return asyncio.run(dispatch(api, core, route_id, param))


def test_sync_view_runs_off_loop_thread_async_view_on_loop():
    api = MasslessAPI()
    loop_tid = threading.get_ident()

    @api.get("/sync")
    def sync_view():
        return {"tid": threading.get_ident()}

    @api.get("/async")
    async def async_view():
        return {"tid": threading.get_ident()}

    # asyncio.run runs the loop on the current thread, so loop_tid is the loop thread.
    sync_raw = _dispatch(api, "/sync")
    async_raw = _dispatch(api, "/async")

    sync_tid = int(sync_raw.rsplit(b'"tid":', 1)[1].rstrip(b"}"))
    async_tid = int(async_raw.rsplit(b'"tid":', 1)[1].rstrip(b"}"))

    assert sync_tid != loop_tid, "sync view must run off the loop thread (on the executor)"
    assert async_tid == loop_tid, "async view must run on the loop thread"


@pytest.mark.django_db(transaction=True)
def test_sync_view_blocking_orm_through_dispatch():
    # A sync (def) view doing a *blocking* ORM read works because it runs on the
    # executor thread, not the loop thread.
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user_model.objects.create_user(username="bob", password="x")
    expected = user_model.objects.count()

    api = MasslessAPI()

    @api.get("/count")
    def count():
        return {"users": get_user_model().objects.count()}

    raw = _dispatch(api, "/count")
    assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
    assert raw.endswith(b'{"users":%d}' % expected)


def test_view_error_logs_and_returns_500_generic_without_debug(caplog):
    api = MasslessAPI()

    @api.get("/boom")
    async def boom():
        raise ValueError("kaboom")

    with override_settings(DEBUG=False), caplog.at_level(logging.ERROR, logger="massless"):
        raw = _dispatch(api, "/boom")

    assert raw.startswith(b"HTTP/1.1 500 ")
    assert raw.endswith(b"Internal Server Error")
    assert b"kaboom" not in raw
    assert any("view error" in rec.message for rec in caplog.records)
    assert any(rec.exc_info for rec in caplog.records)


def test_view_error_debug_includes_traceback():
    api = MasslessAPI()

    @api.get("/boom")
    async def boom():
        raise ValueError("kaboom-debug")

    with override_settings(DEBUG=True):
        raw = _dispatch(api, "/boom")

    assert raw.startswith(b"HTTP/1.1 500 ")
    assert b"kaboom-debug" in raw
    assert b"Traceback" in raw


def test_sync_view_error_also_logged_and_500():
    api = MasslessAPI()

    @api.get("/syncboom")
    def syncboom():
        raise RuntimeError("sync-fail")

    with override_settings(DEBUG=False):
        raw = _dispatch(api, "/syncboom")

    assert raw.startswith(b"HTTP/1.1 500 ")
    assert raw.endswith(b"Internal Server Error")
