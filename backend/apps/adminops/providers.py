from django.core.cache import cache
from django.conf import settings

from .models import ProviderSetting

NAMES = ("flutterwave", "espees")


def is_enabled(name):
    if name == "espees" and not settings.ESPEES_CHECKOUT_READY:
        return False
    v = cache.get(f"provider_enabled:{name}")
    if v is None:
        s = ProviderSetting.objects.filter(provider=name).first()
        v = (name != "espees") if s is None else s.is_enabled
        cache.set(f"provider_enabled:{name}", v, 30)
    return v


def set_enabled(name, enabled):
    ProviderSetting.objects.update_or_create(provider=name, defaults={"is_enabled": enabled})
    cache.delete(f"provider_enabled:{name}")
