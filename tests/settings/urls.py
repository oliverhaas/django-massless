from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.urls import path
from django.views import View


def stream(request):
    # Streaming is not supported until a later phase; massless returns a clear 501.
    return StreamingHttpResponse(iter([b"a", b"b"]))


async def hello(request):
    return JsonResponse({"message": "Hello World", "path": request.path})


async def echo_q(request, item_id: int):
    return JsonResponse({"item_id": item_id, "q": request.GET.get("q")})


def sync_hello(request):
    return HttpResponse(b"sync-ok")


def sync_body_echo(request):
    # A sync view that reads request.body, proving promotion through the chain.
    return HttpResponse(request.body, content_type="application/octet-stream")


async def users_count(request):
    from django.contrib.auth import get_user_model

    count = await get_user_model().objects.acount()
    return JsonResponse({"users": count})


class HelloCBV(View):
    async def get(self, request):
        return JsonResponse({"cbv": True})


# --- lifecycle/ordering test routes (served through the real server) ---
import asyncio  # noqa: E402


async def ok(request):
    return JsonResponse({"ok": True})


async def quick(request):
    return JsonResponse({"quick": True})


async def slow(request):
    await asyncio.sleep(0.3)
    return JsonResponse({"ok": True})


async def slow_id(request, item_id: int):
    await asyncio.sleep(0.2)
    return JsonResponse({"route": "slow", "item_id": item_id})


async def fast_id(request, item_id: int):
    return JsonResponse({"route": "fast", "item_id": item_id})


def sync_ok(request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("", hello),
    path("items/<int:item_id>", echo_q),
    path("sync", sync_hello),
    path("sync-body", sync_body_echo),
    path("users/count", users_count),
    path("cbv", HelloCBV.as_view()),
    path("ok", ok),
    path("quick", quick),
    path("slow", slow),
    path("slow/<int:item_id>", slow_id),
    path("fast/<int:item_id>", fast_id),
    path("sync-json", sync_ok),
    path("stream", stream),
]
