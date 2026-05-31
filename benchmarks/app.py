"""Phase 1 benchmark app: the framework-bound, no-DB, async, no-body endpoints
from benchmarks/cases.md. Run: python -m massless benchmarks.app:api
"""

from massless import MasslessAPI

api = MasslessAPI()

# JSON payload built once at import. range(100) encodes to ~5KB with msgspec, so use
# range(200) (~10.6KB) to match the "10kb" label. Confirm the byte size is close to
# django-bolt's /10k-json payload so the head-to-head comparison stays apples-to-apples.
_TEN_K = [{"id": i, "name": f"item-{i}", "value": i * 7, "active": i % 2 == 0} for i in range(200)]


@api.get("/")
async def root():
    return {"message": "Hello World"}


@api.get("/10k-json")
async def ten_k_json():
    return _TEN_K


@api.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


# Promotion-cost endpoint: the injected request promotes to a real Django
# HttpRequest on first Django-state access (get_host()/method), exercising the
# same promotion path as a real view. Lets the Phase 2 benchmark measure
# promotion overhead vs the non-promoting fast path.
@api.get("/promote-demo")
async def promote_demo(request):
    return {"host": request.get_host(), "method": request.method}
