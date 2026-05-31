"""``python manage.py runmassless <module:api> [--host H] [--port P]
[--processes N] [--workers T]``.

``manage.py`` already calls ``django.setup()``, so settings/apps are loaded and
promotion/ORM/bridge work. Heavy/compiled imports are deferred to ``handle`` so
this command's module import never breaks other management commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = "Run a MasslessAPI app under the massless server (SO_REUSEPORT, N processes)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("target", help="module:attr of the MasslessAPI app")
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--processes", type=int, default=1, help="worker processes (SO_REUSEPORT)")
        parser.add_argument("--workers", type=int, default=None, help="thread-pool size for sync views")

    def handle(self, *args: object, **options: object) -> None:  # noqa: ARG002
        from massless.__main__ import load_app  # noqa: PLC0415
        from massless.server import _serve_target, serve  # noqa: PLC0415
        from massless.supervisor import run_supervised  # noqa: PLC0415

        target = str(options["target"])
        host = str(options["host"])
        port = int(options["port"])  # type: ignore[call-overload]
        processes = int(options["processes"])  # type: ignore[call-overload]
        workers_opt = options["workers"]
        workers = int(workers_opt) if workers_opt is not None else None  # type: ignore[call-overload]

        if processes <= 1:
            api = load_app(target)
            serve(api, host, port, workers)
        else:
            # Each spawned worker re-imports the app and re-bootstraps Django via
            # DJANGO_SETTINGS_MODULE (set in the master's environment by manage.py).
            import os  # noqa: PLC0415

            run_supervised(
                _serve_target,
                target,
                host,
                port,
                workers,
                os.environ.get("DJANGO_SETTINGS_MODULE"),
                processes=processes,
            )
