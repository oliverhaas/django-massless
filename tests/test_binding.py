# tests/test_binding.py
from massless.app import build_binder

# The binder contract is binder(request, path_params, query_getter) -> kwargs.
# A `request`-named view parameter receives the injected request object; all
# other params still bind from path_params/query_getter as before.
_NO_REQUEST = object()


def test_binder_coerces_path_int_and_query_str():
    async def view(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    binder = build_binder(view)
    kwargs = binder(_NO_REQUEST, {"item_id": 12345}, lambda name: "hello" if name == "q" else None)
    assert kwargs == {"item_id": 12345, "q": "hello"}


def test_binder_optional_query_defaults_none():
    async def view(item_id: int, q: str | None = None):
        return {}

    binder = build_binder(view)
    kwargs = binder(_NO_REQUEST, {"item_id": 1}, lambda name: None)
    assert kwargs == {"item_id": 1, "q": None}


def test_binder_no_params():
    async def view():
        return {}

    binder = build_binder(view)
    assert binder(_NO_REQUEST, {}, lambda name: None) == {}


def test_binder_injects_request():
    async def view(request):
        return {}

    sentinel = object()
    binder = build_binder(view)
    kwargs = binder(sentinel, {}, lambda name: None)
    assert kwargs == {"request": sentinel}


def test_binder_request_not_treated_as_query_param():
    # A `request` param must be injected, never read from the query getter.
    queried = []

    def query_getter(name):
        queried.append(name)

    async def view(request, item_id: int, q: str | None = None):
        return {}

    sentinel = object()
    binder = build_binder(view)
    kwargs = binder(sentinel, {"item_id": 7}, query_getter)
    assert kwargs == {"request": sentinel, "item_id": 7, "q": None}
    assert "request" not in queried  # request never goes through the query getter
    assert queried == ["q"]  # only the genuine query param is looked up
