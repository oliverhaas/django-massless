"""Task 4: SO_REUSEPORT socket, serve_async lifecycle (startup/shutdown hooks
sync + async, graceful drain). Tests are deterministic (events, not sleeps) and
bounded (asyncio.wait_for) so they never hang."""

import asyncio
import socket

from massless.app import MasslessAPI
from massless.server import _make_socket, serve_async


def test_make_socket_sets_reuseport_and_two_can_bind_same_port():
    s1 = _make_socket("127.0.0.1", 0)
    try:
        assert s1.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT) == 1
        port = s1.getsockname()[1]
        # A second SO_REUSEPORT socket binds the same (host, port).
        s2 = _make_socket("127.0.0.1", port)
        try:
            assert s2.getsockname()[1] == port
            assert s1.get_inheritable() is True
        finally:
            s2.close()
    finally:
        s1.close()


async def _read_http_response(reader):
    """Read one HTTP/1.1 response by Content-Length (the server keeps the
    connection alive, so reading to EOF would block)."""
    headers = await reader.readuntil(b"\r\n\r\n")
    length = 0
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1].strip())
    body = await reader.readexactly(length) if length else b""
    return headers + body


async def _http_get(host, port, path=b"/"):
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET " + path + b" HTTP/1.1\r\nHost: x\r\n\r\n")
    await writer.drain()
    data = await _read_http_response(reader)
    writer.close()
    return data


def test_serve_async_runs_hooks_serves_and_shuts_down():
    asyncio.run(asyncio.wait_for(_lifecycle_scenario(), timeout=10))


async def _lifecycle_scenario():
    fired = []
    api = MasslessAPI()

    @api.get("/")
    async def root():
        return {"ok": True}

    @api.on_startup
    def boot_sync():
        fired.append("startup_sync")

    @api.on_startup
    async def boot_async():
        fired.append("startup_async")

    @api.on_shutdown
    def stop_sync():
        fired.append("shutdown_sync")

    @api.on_shutdown
    async def stop_async():
        fired.append("shutdown_async")

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    task = asyncio.create_task(serve_async(api, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=1.0))
    await asyncio.wait_for(ready.wait(), timeout=5)

    # Startup hooks fired before ready, in registration order.
    assert fired == ["startup_sync", "startup_async"]

    data = await asyncio.wait_for(_http_get(host, port), timeout=5)
    assert data.startswith(b"HTTP/1.1 200 OK\r\n")
    assert data.endswith(b'{"ok":true}')

    stop.set()
    await asyncio.wait_for(task, timeout=5)

    # Shutdown hooks fired after the server stopped, in registration order.
    assert fired == ["startup_sync", "startup_async", "shutdown_sync", "shutdown_async"]


def test_serve_async_drains_inflight_before_shutdown_hooks():
    asyncio.run(asyncio.wait_for(_drain_scenario(), timeout=10))


async def _drain_scenario():
    events = []
    api = MasslessAPI()
    started = asyncio.Event()

    @api.get("/slow")
    async def slow():
        started.set()
        await asyncio.sleep(0.3)
        events.append("view_done")
        return {"ok": True}

    @api.on_shutdown
    def record():
        events.append("shutdown")

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    task = asyncio.create_task(serve_async(api, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=1.0))
    await asyncio.wait_for(ready.wait(), timeout=5)

    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET /slow HTTP/1.1\r\nHost: x\r\n\r\n")
    await writer.drain()

    # The view started; trigger shutdown while it is in-flight.
    await asyncio.wait_for(started.wait(), timeout=5)
    stop.set()

    data = await asyncio.wait_for(_read_http_response(reader), timeout=5)
    writer.close()
    await asyncio.wait_for(task, timeout=8)

    assert data.endswith(b'{"ok":true}')
    # The in-flight view finished before the shutdown hook ran.
    assert events == ["view_done", "shutdown"]
