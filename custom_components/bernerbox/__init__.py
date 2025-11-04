from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .sensor import BernerBoxCoordinator  # nur die Klasse, kein DOMAIN-Import

DOMAIN = "bernerbox"

# ➕ SWITCH hinzu
PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER, Platform.SWITCH, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = dict(entry.data)  # host, api_key, ids, request_timeout, user_id
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    host: str = data["host"].rstrip("/")
    api_key: str = data["api_key"]
    timeout: int = int(data.get("request_timeout", 6))
    user_id: int = int(data.get("user_id", 1))
    ids = list(map(int, data.get("ids", []))) or list(range(1, 21))

    coordinator = BernerBoxCoordinator(
        hass,
        host=host,
        api_key=api_key,
        user_id=user_id,
        timeout=timeout,
        ids=ids,
    )
    await coordinator.async_config_entry_first_refresh()

    store = hass.data[DOMAIN][entry.entry_id]
    store["coordinator"] = coordinator
    store["names"] = dict(getattr(coordinator, "names", {}))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return ok
