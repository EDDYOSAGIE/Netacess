"""Tiny circuit breaker. After 5 checkout failures within 2 minutes a provider is skipped for 2 minutes,
so customers get the 'use the other method' message instantly instead of waiting on timeouts."""
from django.core.cache import cache

LIMIT, WINDOW = 5, 120


def is_open(name):
    return cache.get(f"breaker:{name}", 0) >= LIMIT


def record_failure(name):
    key = f"breaker:{name}"
    cache.add(key, 0, WINDOW)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, WINDOW)


def reset(name):
    cache.delete(f"breaker:{name}")
