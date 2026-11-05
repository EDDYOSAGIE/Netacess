from django.test import TestCase
from unittest.mock import patch


class HealthCheckTests(TestCase):
    def test_health_check_confirms_database_is_reachable(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok", "cache": "ok"})

    @patch("config.views.cache.set", side_effect=RuntimeError("cache unavailable"))
    def test_health_check_fails_when_cache_is_unavailable(self, cache_set):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        cache_set.assert_called_once()