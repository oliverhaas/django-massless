"""Phase 1 benchmark app: the framework-bound, no-DB, async, no-body endpoints
from benchmarks/cases.md. Run: python -m massless benchmarks.app:api
"""

from massless._request import MasslessRequest, RequestCore

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


# Promotion-cost endpoint: builds a request and forces a one-shot promotion to a
# real Django HttpRequest, then touches Django state (get_host()/META). Lets the
# Phase 2 benchmark measure promotion overhead vs the non-promoting fast path.
# (The Phase 1 dispatch does not inject the per-request object into views, so the
# endpoint constructs a representative request to exercise the same promotion path.)
@api.get("/promote-demo")
async def promote_demo():
    core = RequestCore.py_create(b"GET", b"/promote-demo", b"", [(b"host", b"localhost")], b"")
    request = MasslessRequest(core, {})
    return {"host": request.get_host(), "method": request.META["REQUEST_METHOD"]}
