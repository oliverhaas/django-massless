import urllib.request

import pytest
from django.contrib.auth import get_user_model

from massless.app import MasslessAPI
from tests.test_integration import _serve


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


@pytest.mark.django_db(transaction=True)
def test_view_can_use_orm_through_promoted_request():
    # transaction=True commits to the shared-cache test DB so the server thread's
    # own ORM connection sees the row.
    user_model = get_user_model()
    user_model.objects.create_user(username="alice", password="x")
    expected = user_model.objects.count()

    api = MasslessAPI()

    @api.get("/users/count")
    async def users_count():
        count = await get_user_model().objects.acount()
        return {"users": count}

    base_url, stop = _serve(api)
    try:
        status, body = _get(base_url + "/users/count")
    finally:
        stop()

    assert status == 200
    assert body == b'{"users":%d}' % expected
