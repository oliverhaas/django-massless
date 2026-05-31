# tests/test_binding.py
from massless.app import build_binder


def test_binder_coerces_path_int_and_query_str():
    async def view(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    binder = build_binder(view)
    kwargs = binder({"item_id": 12345}, lambda name: "hello" if name == "q" else None)
    assert kwargs == {"item_id": 12345, "q": "hello"}


def test_binder_optional_query_defaults_none():
    async def view(item_id: int, q: str | None = None):
        return {}

    binder = build_binder(view)
    kwargs = binder({"item_id": 1}, lambda name: None)
    assert kwargs == {"item_id": 1, "q": None}


def test_binder_no_params():
    async def view():
        return {}

    binder = build_binder(view)
    assert binder({}, lambda name: None) == {}
