"""Settings for the shared Django bench app. Lean middleware by default;
BENCH_FULL_MIDDLEWARE=1 enables a production-shape stack (no DB needed: sessions and
messages use cookies). ASGI_THREAD_SENSITIVE=False is honored by the django-asyncio fork
and ignored by stock Django."""

import os

SECRET_KEY = "bench-only-not-secret"
DEBUG = False
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "bench.urls"
USE_TZ = True
ASGI_THREAD_SENSITIVE = False

if os.environ.get("BENCH_FULL_MIDDLEWARE") == "1":
    INSTALLED_APPS = [
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "django.contrib.sessions",
        "django.contrib.messages",
    ]
    MIDDLEWARE = [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ]
    SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
else:
    INSTALLED_APPS: list[str] = []
    MIDDLEWARE: list[str] = []

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# MASSLESS_POOL_LIFECYCLE=1 skips the per-request request_started/request_finished signal
# dispatch (django-bolt style) and returns DB connections directly. Requires a pool with
# CONN_MAX_AGE=0 in real use; the no-DB bench endpoints exercise the signal-skip win.
MASSLESS_POOL_LIFECYCLE = os.environ.get("MASSLESS_POOL_LIFECYCLE") == "1"

# MASSLESS_FAST_MIDDLEWARE=0 disables the chain's fast re-implementation substitution (runs
# every middleware as the real Django class) -- the A/B knob for the FastLayer benchmark.
MASSLESS_FAST_MIDDLEWARE = os.environ.get("MASSLESS_FAST_MIDDLEWARE", "1") == "1"
