"""Framework-bound benchmark endpoints (no DB) shared by every Django-served server
(massless, uvicorn, granian). Paths match django-bolt's bench cases so the same runner
can hit bolt too. Payloads are defined once here so all servers emit identical bytes."""

from django.http import HttpResponse, HttpResponseRedirect, JsonResponse


def _items(n):
    return [{"id": i, "name": f"item-{i}", "value": i * 7, "active": i % 2 == 0} for i in range(n)]


JSON_1K = _items(20)  # ~1 KB
JSON_10K = _items(200)  # ~10 KB
JSON_100K = _items(2000)  # ~100 KB


async def root(request):
    return JsonResponse({"message": "Hello World"})


def sync_root(request):
    return JsonResponse({"message": "Hello World"})


async def json_1k(request):
    return JsonResponse(JSON_1K, safe=False)


async def json_10k(request):
    return JsonResponse(JSON_10K, safe=False)


def sync_json_10k(request):
    return JsonResponse(JSON_10K, safe=False)


async def json_100k(request):
    return JsonResponse(JSON_100K, safe=False)


async def read_item(request, item_id: int):
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})


async def plaintext(request):
    return HttpResponse(b"Hello, World!", content_type="text/plain")


async def html(request):
    return HttpResponse("<html><body><h1>Hello World</h1></body></html>")


async def redirect(request):
    return HttpResponseRedirect("/")


# Fast-tier variants: opt into massless's msgspec-serialized responses (no Django
# HttpResponse object / json.dumps). Same payloads as above for a direct comparison.
from massless import HttpResponse as MHttpResponse  # noqa: E402
from massless import JsonResponse as MJsonResponse  # noqa: E402


async def fast_root(request):
    return MJsonResponse({"message": "Hello World"})


async def fast_json_1k(request):
    return MJsonResponse(JSON_1K)


async def fast_json_10k(request):
    return MJsonResponse(JSON_10K)


async def fast_plaintext(request):
    return MHttpResponse(b"Hello, World!", content_type="text/plain")
