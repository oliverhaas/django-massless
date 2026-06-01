import urllib.request

import pytest
from django.contrib.auth import get_user_model

from massless.handler import MasslessHandler
from tests.test_integration import _serve


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


@pytest.mark.django_db(transaction=True)
def test_view_can_use_orm_through_promoted_request():
    # transaction=True commits to the shared-cache test DB so the server thread's
    # own ORM connection sees the row. The /users/count view runs the async ORM
    # (acount) through Django's chain over the real server.
    user_model = get_user_model()
    user_model.objects.create_user(username="alice", password="x")
    expected = user_model.objects.count()

    handler = MasslessHandler()
    base_url, stop = _serve(handler)
    try:
        status, body = _get(base_url + "/users/count")
    finally:
        stop()

    assert status == 200
    assert body == b'{"users": %d}' % expected
