"""The runmassless Django management command serves the current project: builds a
handler and invokes serve (N=1) or run_supervised (N>1). serve/run_supervised are
patched so no port is bound. Requires `massless` in INSTALLED_APPS (see
tests/settings/base.py)."""

from unittest import mock

from django.core.management import call_command


def test_runmassless_single_process_invokes_serve():
    sentinel_handler = object()
    with (
        mock.patch("massless.handler.MasslessHandler", return_value=sentinel_handler),
        mock.patch("massless.server.serve") as serve,
        mock.patch("massless.supervisor.run_supervised") as supervised,
    ):
        call_command(
            "runmassless",
            "--host",
            "127.0.0.1",
            "--port",
            "8456",
            "--processes",
            "1",
            "--workers",
            "6",
        )

    serve.assert_called_once_with(sentinel_handler, "127.0.0.1", 8456, 6)
    supervised.assert_not_called()


def test_runmassless_multi_process_invokes_supervisor():
    with (
        mock.patch("massless.server.serve") as serve,
        mock.patch("massless.supervisor.run_supervised") as supervised,
    ):
        call_command("runmassless", "--port", "8457", "--processes", "2")

    serve.assert_not_called()
    supervised.assert_called_once()
    call = supervised.call_args
    from massless.server import _serve_target

    assert call.args[0] is _serve_target
    assert call.args[2] == 8457
    assert call.kwargs["processes"] == 2


def test_runmassless_defaults():
    sentinel_handler = object()
    with (
        mock.patch("massless.handler.MasslessHandler", return_value=sentinel_handler),
        mock.patch("massless.server.serve") as serve,
    ):
        call_command("runmassless")

    serve.assert_called_once_with(sentinel_handler, "127.0.0.1", 8000, None)
