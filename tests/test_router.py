# tests/test_router.py
from massless._router import Router


def test_static_hit_returns_route_id_and_no_param():
    r = Router()
    r.add_static(b"/", 0)
    r.add_static(b"/10k-json", 1)
    assert r.match(b"/") == (0, -1)
    assert r.match(b"/10k-json") == (1, -1)


def test_static_miss_returns_minus_one():
    r = Router()
    r.add_static(b"/", 0)
    assert r.match(b"/nope") == (-1, -1)
