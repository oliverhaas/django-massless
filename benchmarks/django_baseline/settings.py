"""Minimal Django settings for the framework-overhead baseline.

Plain Django ASGI with an empty middleware stack and no apps: this measures
Django's core request/response path (ASGIHandler + URL resolver + view +
JsonResponse) without any framework on top. It is the floor that massless and
django-bolt are measured against on framework-bound endpoints.
"""

SECRET_KEY = "benchmark-only-not-secret"
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "benchmarks.django_baseline.urls"
DEBUG = False
INSTALLED_APPS: list[str] = []
MIDDLEWARE: list[str] = []
USE_TZ = True
