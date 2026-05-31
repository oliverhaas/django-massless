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


def test_per_route_middleware_and_bridge_recorded():
    m1, m2 = object(), object()
    api = MasslessAPI()

    @api.get("/x", middleware=[m1, m2], bridge=True)
    async def x():
        return {}

    rid = api.build_router().match(b"/x")[0]
    route = api.routes[rid]
    assert route.middleware == [m1, m2]
    assert route.bridge is True


def test_global_default_middleware_prepended():
    g = object()
    r = object()
    api = MasslessAPI(middleware=[g])

    @api.get("/y", middleware=[r])
    async def y():
        return {}

    @api.get("/z")
    async def z():
        return {}

    routes = {route.path: route for route in api.routes}
    # Global default is prepended; route-specific follows.
    assert routes["/y"].middleware == [g, r]
    assert routes["/z"].middleware == [g]
    assert routes["/z"].bridge is False


def test_route_is_async_flag():
    api = MasslessAPI()

    @api.get("/a")
    async def a():
        return {}

    @api.get("/s")
    def s():
        return {}

    routes = {route.path: route for route in api.routes}
    assert routes["/a"].is_async is True
    assert routes["/s"].is_async is False


def test_startup_shutdown_hook_registries():
    api = MasslessAPI()

    @api.on_startup
    def boot():
        return None

    @api.on_shutdown
    async def stop():
        return None

    assert api.on_startup_hooks == [boot]
    assert api.on_shutdown_hooks == [stop]
    # The decorator returns the callable unchanged.
    assert boot() is None
