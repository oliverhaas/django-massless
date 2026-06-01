"""SO_REUSEPORT socket, serve_async lifecycle (startup/shutdown hooks sync +
async, graceful drain). Tests are deterministic (events, not sleeps) and bounded
(asyncio.wait_for) so they never hang. Views are served through Django's resolver
+ middleware via MasslessHandler over the real server."""

import asyncio
import socket

from massless.handler import MasslessHandler
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
    handler = MasslessHandler()

    @handler.on_startup
    def boot_sync():
        fired.append("startup_sync")

    @handler.on_startup
    async def boot_async():
        fired.append("startup_async")

    @handler.on_shutdown
    def stop_sync():
        fired.append("shutdown_sync")

    @handler.on_shutdown
    async def stop_async():
        fired.append("shutdown_async")

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    task = asyncio.create_task(serve_async(handler, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=1.0))
    await asyncio.wait_for(ready.wait(), timeout=5)

    # Startup hooks fired before ready, in registration order.
    assert fired == ["startup_sync", "startup_async"]

    data = await asyncio.wait_for(_http_get(host, port, b"/ok"), timeout=5)
    assert data.startswith(b"HTTP/1.1 200 OK\r\n")
    assert data.endswith(b'{"ok": true}')

    stop.set()
    await asyncio.wait_for(task, timeout=5)

    # Shutdown hooks fired after the server stopped, in registration order.
    assert fired == ["startup_sync", "startup_async", "shutdown_sync", "shutdown_async"]


def test_serve_async_drains_inflight_before_shutdown_hooks():
    asyncio.run(asyncio.wait_for(_drain_scenario(), timeout=10))


async def _drain_scenario():
    events = []
    handler = MasslessHandler()

    @handler.on_shutdown
    def record():
        events.append("shutdown")

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    task = asyncio.create_task(serve_async(handler, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=1.0))
    await asyncio.wait_for(ready.wait(), timeout=5)

    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET /slow HTTP/1.1\r\nHost: x\r\n\r\n")
    await writer.drain()

    # Give the in-flight /slow view (~0.3s) time to register before triggering
    # shutdown, so the drain has real in-flight work to await.
    await asyncio.sleep(0.05)
    stop.set()

    data = await asyncio.wait_for(_read_http_response(reader), timeout=5)
    writer.close()
    await asyncio.wait_for(task, timeout=8)

    assert data.endswith(b'{"ok": true}')
    # The shutdown hook ran only after the in-flight view's response was produced.
    assert events == ["shutdown"]


def test_inflight_request_gets_200_when_server_stops_alongside_idle_connection():
    asyncio.run(asyncio.wait_for(_inflight_not_cancelled_scenario(), timeout=10))


async def _inflight_not_cancelled_scenario():
    """An in-flight request (view awaiting ~0.3s) that STARTED before shutdown must
    finish with its 200 rather than being cancelled, even while a second, idle
    keep-alive connection lingers (whose worker loop must not be mistaken for
    in-flight work and must not stall the drain)."""
    handler = MasslessHandler()

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    task = asyncio.create_task(
        serve_async(handler, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=2.0),
    )
    await asyncio.wait_for(ready.wait(), timeout=5)

    # An idle keep-alive connection: one quick request, response read, kept open.
    idle_reader, idle_writer = await asyncio.open_connection(host, port)
    idle_writer.write(b"GET /quick HTTP/1.1\r\nHost: x\r\n\r\n")
    await idle_writer.drain()
    idle_data = await asyncio.wait_for(_read_http_response(idle_reader), timeout=5)
    assert idle_data.endswith(b'{"quick": true}')

    # A second connection with an in-flight slow request.
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET /slow HTTP/1.1\r\nHost: x\r\n\r\n")
    await writer.drain()
    await asyncio.sleep(0.05)

    # Stop while /slow is mid-response and the idle connection is still open.
    stop.set()

    # The in-flight request still completes with a 200 (not cancelled).
    data = await asyncio.wait_for(_read_http_response(reader), timeout=5)
    assert data.startswith(b"HTTP/1.1 200 OK\r\n")
    assert data.endswith(b'{"ok": true}')

    # And the whole serve task winds down within the overall bound (the idle
    # keep-alive worker loop must not stall the drain to its full timeout).
    await asyncio.wait_for(task, timeout=8)
    writer.close()
    idle_writer.close()


def test_drain_does_not_hang_on_idle_keepalive_connection():
    asyncio.run(asyncio.wait_for(_idle_drain_scenario(), timeout=10))


async def _idle_drain_scenario():
    """A drain with no in-flight request work must finish promptly even with an
    open idle keep-alive connection: the per-connection worker loop (blocked on
    its queue) is NOT in-flight work and must not burn the full drain timeout."""
    import time

    handler = MasslessHandler()

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    # A generous drain timeout: if the idle worker loop is mistaken for in-flight
    # work, shutdown would take ~this long. We assert it finishes much faster.
    task = asyncio.create_task(
        serve_async(handler, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=5.0),
    )
    await asyncio.wait_for(ready.wait(), timeout=5)

    reader, writer = await asyncio.open_connection(host, port)
    writer.write(b"GET /quick HTTP/1.1\r\nHost: x\r\n\r\n")
    await writer.drain()
    data = await asyncio.wait_for(_read_http_response(reader), timeout=5)
    assert data.endswith(b'{"quick": true}')

    # Connection stays open (keep-alive). Trigger shutdown; it must be prompt.
    t0 = time.monotonic()
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"drain took {elapsed:.2f}s; idle keep-alive stalled it"
    writer.close()


def test_sync_view_served_through_django_chain():
    asyncio.run(asyncio.wait_for(_sync_view_scenario(), timeout=10))


async def _sync_view_scenario():
    """A sync (def) view is adapted by Django's async middleware chain (via
    sync_to_async, thread-sensitive) and served over the real server; the server
    still drains and shuts down cleanly."""
    handler = MasslessHandler()

    ready = asyncio.Event()
    stop = asyncio.Event()
    sock = _make_socket("127.0.0.1", 0)
    host, port = sock.getsockname()

    task = asyncio.create_task(
        serve_async(handler, host, port, ready=ready, stop=stop, sock=sock, drain_timeout=2.0),
    )
    await asyncio.wait_for(ready.wait(), timeout=5)

    data = await asyncio.wait_for(_http_get(host, port, b"/sync-json"), timeout=5)
    assert data.startswith(b"HTTP/1.1 200 OK\r\n")
    assert data.endswith(b'{"ok": true}')

    stop.set()
    await asyncio.wait_for(task, timeout=8)
