"""Benchmark app (drop-in pivot): a minimal *normal* Django project served through
massless. The bolt-style MasslessAPI surface is retired; this is a plain ROOT_URLCONF
with async + sync views. The full benchmark pivot (massless vs uvicorn+Django /
uvicorn+ninja) lands in a later phase.

Run (once wired into a settings module):
    python -m massless --settings benchmarks.settings --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from django.http import HttpResponse, JsonResponse
from django.urls import path

# JSON payload built once at import (~10.6KB) for the throughput case.
_TEN_K = [{"id": i, "name": f"item-{i}", "value": i * 7, "active": i % 2 == 0} for i in range(200)]


async def root(request):
    return JsonResponse({"message": "Hello World"})


async def ten_k_json(request):
    return JsonResponse(_TEN_K, safe=False)


async def read_item(request, item_id: int):
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})


def sync_hello(request):
    return HttpResponse(b'{"message": "Hello World"}', content_type="application/json")


urlpatterns = [
    path("", root),
    path("10k-json", ten_k_json),
    path("items/<int:item_id>", read_item),
    path("sync-hello", sync_hello),
]
