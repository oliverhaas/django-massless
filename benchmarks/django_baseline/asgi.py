"""ASGI entrypoint for the plain-Django baseline.

Run single-process with:
    uvicorn benchmarks.django_baseline.asgi:application --port 8002 --workers 1
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "benchmarks.django_baseline.settings")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
