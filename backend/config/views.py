import logging
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        cache_key = f"health-check:{uuid.uuid4().hex}"
        cache.set(cache_key, "ok", timeout=10)
        cache_ok = cache.get(cache_key) == "ok"
        cache.delete(cache_key)
        if not cache_ok:
            raise RuntimeError("Cache read-after-write failed")
    except Exception as exc:
        log.error("Readiness check failed (%s)", type(exc).__name__)
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok", "cache": "ok"})