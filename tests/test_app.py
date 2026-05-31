from massless.app import MasslessAPI


def test_register_and_compile_static_and_dynamic():
    api = MasslessAPI()

    @api.get("/")
    async def root():
        return {"message": "Hello World"}

    @api.get("/items/{item_id}")
    async def item(item_id: int, q: str | None = None):
        return {"item_id": item_id, "q": q}

    router = api.build_router()
    assert router.match(b"/")[0] != -1
    rid, param = router.match(b"/items/12345")
    assert rid != -1 and param == 12345
    # The compiled route exposes its view and binder by id.
    route = api.routes[rid]
    assert route.view is item
    # binder contract: binder(request, path_params, query_getter) -> kwargs.
    assert route.binder(None, {"item_id": 12345}, lambda n: "x")["item_id"] == 12345
