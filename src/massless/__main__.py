"""Run a MasslessAPI app: python -m massless module:attr --host H --port P
[--processes N] [--workers T].

``--processes 1`` serves in-process (dev/tests). ``--processes N>1`` delegates to
the supervisor, which spawns N workers sharing the port via SO_REUSEPORT. Spawned
workers do NOT inherit this process's imported app, so the worker target re-imports
it from ``module:attr`` and re-bootstraps Django before serving.
"""

from __future__ import annotations

import argparse
import importlib
import os
from typing import TYPE_CHECKING

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="massless")
    parser.add_argument("target", help="module:attr of the MasslessAPI app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--processes", type=int, default=1, help="worker processes (SO_REUSEPORT)")
    parser.add_argument("--workers", type=int, default=None, help="thread-pool size for sync views")
    parser.add_argument(
        "--settings",
        default=None,
        help="DJANGO_SETTINGS_MODULE to configure before serving (enables promotion + ORM)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    from massless.server import _serve_target, serve  # noqa: PLC0415
    from massless.supervisor import run_supervised  # noqa: PLC0415

    args = build_parser().parse_args(argv)
    if args.processes <= 1:
        _bootstrap_django(args.settings)
        api = load_app(args.target)
        serve(api, args.host, args.port, args.workers)
    else:
        # The master itself does not need Django; each worker re-bootstraps it.
        run_supervised(
            _serve_target,
            args.target,
            args.host,
            args.port,
            args.workers,
            args.settings,
            processes=args.processes,
        )


if __name__ == "__main__":
    main()
