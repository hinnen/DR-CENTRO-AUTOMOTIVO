"""Leitura das preferências operacionais (singleton WorkshopSettings)."""

from functools import lru_cache

from apps.core.models import WorkshopSettings


@lru_cache(maxsize=1)
def get_workshop_settings() -> WorkshopSettings:
    return WorkshopSettings.load()


def invalidate_workshop_settings_cache() -> None:
    get_workshop_settings.cache_clear()


def reception_can_create_mechanic() -> bool:
    return get_workshop_settings().reception_can_create_mechanic


def auto_whatsapp_status_notify() -> bool:
    return get_workshop_settings().auto_whatsapp_status_notify
