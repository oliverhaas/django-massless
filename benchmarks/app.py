"""Phase 1 benchmark app: the framework-bound, no-DB, async, no-body endpoints
from benchmarks/cases.md. Run: python -m massless benchmarks.app:api
"""

from massless._middleware import CORS, JWTAuth, RateLimit

from massless import MasslessAPI

# Shared secret for the JWT bench endpoints (matches django-bolt's /auth/context case).
_JWT_SECRET = "bench-secret"

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


# --- Phase 3 fast-tier middleware endpoints ---


# JWT validated, no DB, no promotion: reads only request.auth. Head-to-head with
# django-bolt's /auth/context.
@api.get("/auth/context", middleware=[JWTAuth(secret=_JWT_SECRET)])
async def auth_context(request):
    return {"sub": request.auth["sub"], "scope": request.auth.get("scope")}


# Promotes + ORM user load: reads request.user (resolves via the user model).
@api.get("/auth/me", middleware=[JWTAuth(secret=_JWT_SECRET)])
async def auth_me(request):
    user = await request.aget_user()
    return {"id": user.pk, "username": getattr(user, "username", None)}


# CORS-wrapped route: preflight 204 on the fast path; actual responses carry the
# Access-Control-Allow-Origin header.
@api.get("/cors/ping", middleware=[CORS(allow_origins=["*"])])
async def cors_ping():
    return {"pong": True}


# Rate-limited route: 429 after the limit on the fast path.
@api.get("/limited", middleware=[RateLimit(limit=100, window_s=1)])
async def limited():
    return {"ok": True}


# Sync (def) view: dispatched on the thread-pool executor, off the loop thread.
# Exercises the Phase 4 executor path for the sync-vs-async benchmark.
@api.get("/sync-hello")
def sync_hello():
    return {"message": "Hello World"}
