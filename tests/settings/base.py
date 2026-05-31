SECRET_KEY = "test-secret-key"

# Promotion + parity exercise get_host(), which validates against ALLOWED_HOSTS.
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
]

import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        # A file-based test DB (not :memory:) so the cross-thread ORM-through-server
        # test sees the same database from the server's own uvloop-thread connection.
        # A file path also stays xdist-safe: Django appends the worker suffix to this
        # NAME, yielding a distinct file per worker (whereas a shared-cache URI would
        # break when the suffix landed inside the query string).
        "TEST": {"NAME": str(Path(tempfile.gettempdir()) / "massless_test_db.sqlite3")},
    },
}

USE_TZ = True
