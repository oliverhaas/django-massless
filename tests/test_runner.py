"""Task 6: __main__ CLI parsing + dispatch to serve (N=1) vs run_supervised (N>1).
serve/run_supervised are patched so nothing actually binds a port."""

from unittest import mock

from massless import __main__ as runner


def test_build_parser_accepts_processes_and_workers():
    args = runner.build_parser().parse_args(
        ["benchmarks.app:api", "--host", "198.51.100.7", "--port", "9001", "--processes", "3", "--workers", "8"],
    )
    assert args.target == "benchmarks.app:api"
    assert args.host == "198.51.100.7"
    assert args.port == 9001
    assert args.processes == 3
    assert args.workers == 8


def test_defaults():
    args = runner.build_parser().parse_args(["m:api"])
    assert args.processes == 1
    assert args.workers is None
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_single_process_calls_serve():
    sentinel_api = object()
    with (
        mock.patch.object(runner, "load_app", return_value=sentinel_api) as load,
        mock.patch.object(runner, "_bootstrap_django"),
        mock.patch("massless.server.serve") as serve,
        mock.patch("massless.supervisor.run_supervised") as supervised,
    ):
        runner.main(
            ["benchmarks.app:api", "--host", "127.0.0.1", "--port", "8123", "--processes", "1", "--workers", "4"],
        )

    load.assert_called_once_with("benchmarks.app:api")
    serve.assert_called_once_with(sentinel_api, "127.0.0.1", 8123, 4)
    supervised.assert_not_called()


def test_multi_process_calls_run_supervised():
    with (
        mock.patch("massless.server.serve") as serve,
        mock.patch("massless.supervisor.run_supervised") as supervised,
    ):
        runner.main(["benchmarks.app:api", "--port", "8200", "--processes", "2", "--workers", "5"])

    serve.assert_not_called()
    supervised.assert_called_once()
    from massless.server import _serve_target

    call = supervised.call_args
    # target + positional args, then processes kwarg.
    assert call.args[0] is _serve_target
    assert call.args[1] == "benchmarks.app:api"
    assert call.args[2] == "127.0.0.1"  # default host
    assert call.args[3] == 8200
    assert call.args[4] == 5  # workers
    assert call.kwargs["processes"] == 2
