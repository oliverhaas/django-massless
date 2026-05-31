"""Plain-Django async views mirroring the Phase 1 framework-bound endpoints."""

from django.http import HttpRequest, JsonResponse

# Same shape as the massless bench-app payload (~10KB encoded).
_TEN_K = [{"id": i, "name": f"item-{i}", "value": i * 7, "active": i % 2 == 0} for i in range(200)]


async def root(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"message": "Hello World"})


async def ten_k_json(request: HttpRequest) -> JsonResponse:
    return JsonResponse(_TEN_K, safe=False)


async def read_item(request: HttpRequest, item_id: int) -> JsonResponse:
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})
