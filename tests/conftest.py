"""Pytest configuration."""

import pytest


@pytest.fixture
def allow_db_connection_management(django_db_blocker):
    """Permit DB connection bookkeeping for tests that drive a full massless request.

    dispatch() fires Django's request_started/request_finished signals, whose receivers
    (close_old_connections, reset_queries) run in the shared thread-sensitive executor.
    A prior DB-using test can leave an initialized connection in that executor thread, so
    the bookkeeping touches the connection; pytest-django would otherwise block it. This
    only unblocks access (no transaction wrapping), matching what a real worker does.
    """
    with django_db_blocker.unblock():
        yield
