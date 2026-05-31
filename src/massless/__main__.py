"""Run a MasslessAPI app: python -m massless module:attr --host H --port P."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
from typing import TYPE_CHECKING

import uvloop

from massless._protocol import MasslessProtocol

if TYPE_CHECKING:
    from massless.app import MasslessAPI


def _bootstrap_django(settings_module: str | None) -> None:
    if settings_module:
        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        # Deferred import: fast-path-only apps run without Django configured, so
        # django is only imported once settings are present.
        import django  # noqa: PLC0415

        django.setup()


def load_app(target: str) -> MasslessAPI:
    module_name, _, attr = target.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr or "api")


async def serve(api: MasslessAPI, host: str, port: int) -> None:
    router = api.build_router()
    loop = asyncio.get_running_loop()
    server = await loop.create_server(lambda: MasslessProtocol(api, router), host, port)
    async with server:
        await server.serve_forever()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="massless")
    parser.add_argument("target", help="module:attr of the MasslessAPI app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--settings",
        default=None,
        help="DJANGO_SETTINGS_MODULE to configure before serving (enables promotion + ORM)",
    )
    args = parser.parse_args(argv)
    _bootstrap_django(args.settings)
    api = load_app(args.target)
    uvloop.run(serve(api, args.host, args.port))


if __name__ == "__main__":
    main()
