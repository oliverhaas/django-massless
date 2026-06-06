"""RSGI entrypoint for granian. get_rsgi_application() is provided by the django-asyncio
fork; this entrypoint is only used when the fork is the installed Django."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.settings")

from django.core.rsgi import get_rsgi_application

application = get_rsgi_application()
