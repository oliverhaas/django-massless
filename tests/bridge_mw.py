"""Test middleware used by the bridge tier tests. Lives in a tests module so the
bridge integration test can reference it via a dotted path in settings.MIDDLEWARE.
"""

from asgiref.sync import iscoroutinefunction, markcoroutinefunction


class AddHeaderMiddleware:
    """Sync middleware: reads request.path and sets a response header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Prove the middleware observes the (promoted) request.
        request._bridge_saw_path = request.path
        response = self.get_response(request)
        response["X-Bridge"] = "1"
        response["X-Bridge-Path"] = request.path
        return response


class SetCookieMiddleware:
    """Sync middleware: sets a cookie on the response (lands in response.cookies,
    not response.headers), to prove Set-Cookie survives the bridge."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.set_cookie("sid", "abc")
        return response


class AsyncAddHeaderMiddleware:
    """Async middleware variant: async_capable, sets a header asynchronously."""

    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    async def __call__(self, request):
        request._bridge_saw_path = request.path
        response = await self.get_response(request)
        response["X-Bridge-Async"] = "1"
        response["X-Bridge-Path"] = request.path
        return response
