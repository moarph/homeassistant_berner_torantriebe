from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _get_json(session, url: str, timeout: int):
    try:
        async with session.get(url, timeout=timeout, headers={"Accept":"application/json"}) as resp:
            txt = await resp.text()
            if resp.status != 200:
                _LOGGER.debug("SSH GET %s -> %s %s", url, resp.status, txt[:200])
                return None
            return await resp.json(content_type=None)
    except Exception as e:
        _LOGGER.debug("SSH GET fail %s (%s)", url, e)
        return None


async def _post_form_bool(session, url: str, form: Dict[str, str], timeout: int) -> bool:
    """POST x-www-form-urlencoded, Erfolg wenn HTTP 200 und true/OK."""
    try:
        async with session.post(
            url, data=form, timeout=timeout,
            headers={"Accept":"application/json", "Content-Type":"application/x-www-form-urlencoded"}
        ) as resp:
            text = await resp.text()
            _LOGGER.debug("SSH POST %s form=%s -> %s %s", url, form, resp.status, text[:200])
            if resp.status != 200:
                return False
            lt = text.strip().lower()
            return lt == "true" or '"status":"ok"' in lt
    except Exception as e:
        _LOGGER.debug("SSH POST fail %s (%s)", url, e)
        return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    host: str = data["host"].rstrip("/")
    api_key: str = data["api_key"]
    timeout: int = int(data.get("request_timeout", 6))

    entity = BernerBoxSshSwitch(entry_id=entry.entry_id, host=host, api_key=api_key, timeout=timeout)
    async_add_entities([entity])


class BernerBoxSshSwitch(SwitchEntity):
    """Schalter für SSH Zugriff (on/off) auf der Box."""

    _attr_should_poll = False  # wir aktualisieren aktiv bei Änderungen

    def __init__(self, *, entry_id: str, host: str, api_key: str, timeout: int):
        self._entry_id = entry_id
        self._host = host
        self._api_key = api_key
        self._timeout = int(timeout)

        self._is_on: Optional[bool] = None

        self._attr_name = "SSH Zugriff"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-ssh-access"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-box")},
            name="BERNER-BOX",
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )

    @property
    def is_on(self) -> Optional[bool]:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        await self._refresh_state()

    async def _refresh_state(self) -> None:
        """Liest ssh_access aus den BoxSettings."""
        session = async_get_clientsession(self.hass)
        url = f"{self._host}/api/v1/BoxSettings/getAllSettings?api_key={self._api_key}&format=json"
        data = await _get_json(session, url, self._timeout)
        val = None
        if isinstance(data, list):
            for row in data:
                try:
                    if str(row.get("name")) == "ssh_access":
                        rv = str(row.get("value", "")).strip().lower()
                        val = (rv in ("1", "true", "on", "yes"))
                        break
                except Exception:
                    continue

        if val is not None:
            self._is_on = val
        # Bei None behalten wir den alten Zustand (falls vorhanden)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._send_mode("on")

    async def async_turn_off(self, **kwargs) -> None:
        await self._send_mode("off")

    async def _send_mode(self, mode: str) -> None:
        session = async_get_clientsession(self.hass)
        url = f"{self._host}/api/v1/Box/toggleSSHAccess?api_key={self._api_key}&format=json"
        ok = await _post_form_bool(session, url, {"mode": mode}, self._timeout)
        if not ok:
            _LOGGER.warning("BernerBox: SSH %s fehlgeschlagen", mode)
            return
        # Erfolgreich -> Zustand sofort anpassen und einmal nachlesen
        self._is_on = (mode == "on")
        self.async_write_ha_state()
        await self._refresh_state()
