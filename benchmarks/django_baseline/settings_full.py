"""Same baseline Django app, but with a realistic default middleware stack.

Used to benchmark the *full-fidelity* drop-in path (where stock middleware promotes
the lazy request), as opposed to settings.py's empty-middleware lean path.
"""

from benchmarks.django_baseline.settings import *  # noqa: F403

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]
