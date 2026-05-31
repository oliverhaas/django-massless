"""Run a MasslessAPI app: python -m massless module:attr --host H --port P."""

from __future__ import annotations

import argparse
import asyncio
import importlib
from typing import TYPE_CHECKING

import uvloop

from massless._protocol import MasslessProtocol

if TYPE_CHECKING:
    from massless.app import MasslessAPI


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
    args = parser.parse_args(argv)
    api = load_app(args.target)
    uvloop.run(serve(api, args.host, args.port))


if __name__ == "__main__":
    main()
