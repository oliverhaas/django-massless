"""__main__ CLI parsing + dispatch to serve (N=1) vs run_supervised (N>1).
serve/run_supervised are patched so nothing actually binds a port; the handler is
patched so building it does not require live settings."""

from unittest import mock

from massless import __main__ as runner


def test_build_parser_accepts_processes_and_workers():
    args = runner.build_parser().parse_args(
        ["--host", "198.51.100.7", "--port", "9001", "--processes", "3", "--workers", "8"],
    )
    assert args.host == "198.51.100.7"
    assert args.port == 9001
    assert args.processes == 3
    assert args.workers == 8


def test_defaults():
    args = runner.build_parser().parse_args([])
    assert args.processes == 1
    assert args.workers is None
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.settings is None


def test_single_process_calls_serve():
    sentinel_handler = object()
    with (
        mock.patch.object(runner, "_bootstrap_django"),
        mock.patch("massless.handler.MasslessHandler", return_value=sentinel_handler),
        mock.patch("massless.server.serve") as serve,
        mock.patch("massless.supervisor.run_supervised") as supervised,
    ):
        runner.main(["--host", "127.0.0.1", "--port", "8123", "--processes", "1", "--workers", "4"])

    serve.assert_called_once_with(sentinel_handler, "127.0.0.1", 8123, 4)
    supervised.assert_not_called()


def test_main_single_process_serves_with_handler():
    with (
        mock.patch.object(runner, "_bootstrap_django"),
        mock.patch("massless.handler.MasslessHandler"),
        mock.patch("massless.server.serve") as serve,
    ):
        runner.main(["--host", "127.0.0.1", "--port", "0", "--processes", "1"])
    assert serve.called


def test_multi_process_calls_run_supervised():
    with (
        mock.patch("massless.server.serve") as serve,
        mock.patch("massless.supervisor.run_supervised") as supervised,
    ):
        runner.main(["--port", "8200", "--processes", "2", "--workers", "5", "--settings", "settings.base"])

    serve.assert_not_called()
    supervised.assert_called_once()
    from massless.server import _serve_target

    call = supervised.call_args
    # target + positional args, then processes kwarg.
    assert call.args[0] is _serve_target
    assert call.args[1] == "127.0.0.1"  # default host
    assert call.args[2] == 8200
    assert call.args[3] == 5  # workers
    assert call.args[4] == "settings.base"  # settings
    assert call.kwargs["processes"] == 2
