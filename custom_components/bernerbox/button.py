from __future__ import annotations

import asyncio
import logging
from typing import List, Dict

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# ----------------------- HTTP helpers -----------------------
async def _get_json(session, url: str, timeout: int):
    try:
        async with session.get(url, timeout=timeout, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                txt = await resp.text()
                _LOGGER.debug("GET %s -> %s %s", url, resp.status, txt[:200])
                return None
            return await resp.json(content_type=None)
    except Exception as e:
        _LOGGER.debug("GET fail %s (%s)", url, e)
        return None


async def _post_ok(session, url: str, payload: dict, timeout: int) -> bool:
    try:
        async with session.post(
            url,
            json=payload,
            timeout=timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        ) as resp:
            text = await resp.text()
            _LOGGER.debug("POST %s payload=%s -> %s %s", url, payload, resp.status, text[:200])
            return resp.status == 200 and ('"status":"OK"' in text or '"funk_command_executed"' in text)
    except Exception as e:
        _LOGGER.debug("POST %s failed: %s", url, e)
        return False


async def _call_update(session, url: str, timeout: int) -> bool:
    """
    Für @url UPDATE ... Routen: POST + X-HTTP-Method-Override: UPDATE.
    Erfolg: HTTP 200 und Body enthält true/OK.
    """
    try:
        async with session.post(
            url,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "X-HTTP-Method-Override": "UPDATE",
            },
        ) as resp:
            text = await resp.text()
            _LOGGER.debug("UPDATE %s -> %s %s", url, resp.status, text[:200])
            if resp.status != 200:
                return False
            # Restler kann boolean true oder JSON liefern
            lt = text.strip().lower()
            return lt == "true" or '"status":"ok"' in lt
    except Exception as e:
        _LOGGER.debug("UPDATE call failed %s (%s)", url, e)
        return False


# ----------------------- Setup ------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    host: str = data["host"].rstrip("/")
    api_key: str = data["api_key"]
    timeout: int = int(data.get("request_timeout", 6))
    user_id: int = int(data.get("user_id", 1))
    ids: List[int] = list(map(int, data.get("ids", []))) or list(range(1, 21))

    session = async_get_clientsession(hass)

    # Namen EINMAL laden und cachen (stabil; nicht zur Laufzeit überschreiben)
    names_map: Dict[int, str] = {}
    url_list = f"{host}/api/item/getItemsByUser.json/{user_id}?api_key={api_key}"
    lst = await _get_json(session, url_list, timeout)
    if isinstance(lst, list):
        for it in lst:
            try:
                iid = int(it.get("id_item"))
                nm = str(it.get("name") or f"Item {iid}")
                names_map[iid] = nm
            except Exception:
                continue
    for iid in ids:
        names_map.setdefault(iid, f"Item {iid}")

    hass.data[DOMAIN][entry.entry_id]["names"] = names_map

    entities: List[ButtonEntity] = []

    # ✅ 1) Globaler Refresh-Button
    entities.append(
        BernerBoxRefreshButton(
            entry_id=entry.entry_id, host=host, api_key=api_key, user_id=user_id, timeout=timeout
        )
    )

    # ✅ 2) Reboot-Button (Box neu starten)
    entities.append(
        BernerBoxRebootButton(
            entry_id=entry.entry_id, host=host, api_key=api_key, timeout=timeout
        )
    )

    # ✅ 3) Impuls-Buttons pro Item
    for item_id in ids:
        name = names_map.get(item_id, f"Item {item_id}")
        entities.append(
            BernerBoxImpulseButton(
                entry_id=entry.entry_id,
                host=host,
                api_key=api_key,
                name=name,
                item_id=item_id,
                func_id=item_id,
                timeout=timeout,
            )
        )

    async_add_entities(entities)
    _LOGGER.info("BernerBox: %d Button-Entity(s) registriert (%d Impulse + Refresh + Reboot)", len(entities), len(ids))


# ----------------------- Entities ---------------------------
class BernerBoxRefreshButton(ButtonEntity):
    """Box-weiter Button: stößt updateAllItemsByUser an und aktualisiert den Coordinator."""
    def __init__(self, *, entry_id: str, host: str, api_key: str, user_id: int, timeout: int):
        self._entry_id = entry_id
        self._host = host
        self._api_key = api_key
        self._user_id = int(user_id)
        self._timeout = int(timeout)

        self._attr_name = "Status aktualisieren"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-box")},
            name="BERNER-BOX",
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )

    async def async_press(self) -> None:
        entry_data = self.hass.data[DOMAIN][self._entry_id]
        coordinator = entry_data.get("coordinator")
        if coordinator is None or not hasattr(coordinator, "schedule_updateall"):
            return
        coordinator.schedule_updateall(0)
        coordinator.schedule_updateall(25)
        async def _delayed():
            await asyncio.sleep(4)
            await coordinator.async_request_refresh()
        self.hass.async_create_task(_delayed())


class BernerBoxRebootButton(ButtonEntity):
    """Startet die Box per API neu (admin-geschützte Route)."""
    def __init__(self, *, entry_id: str, host: str, api_key: str, timeout: int):
        self._entry_id = entry_id
        self._host = host
        self._api_key = api_key
        self._timeout = int(timeout)

        self._attr_name = "Box neu starten"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-reboot"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-box")},
            name="BERNER-BOX",
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )

    async def async_press(self) -> None:
        session = async_get_clientsession(self.hass)
        url = f"{self._host}/api/v1/Box/restartSystem?api_key={self._api_key}&format=json"
        ok = await _call_update(session, url, self._timeout)
        if not ok:
            _LOGGER.warning("BernerBox: Reboot fehlgeschlagen (HTTP/Route)")
        # Hinweis: Gerät rebootet asynchron; UI meldet keinen Abschluss zurück.


class BernerBoxImpulseButton(ButtonEntity):
    """Momentkontakt als Button (führt einen Impuls aus) und plant Status-Updates wie die App."""
    def __init__(self, entry_id: str, host: str, api_key: str, name: str, item_id: int, func_id: int, timeout: int):
        self._entry_id = entry_id
        self._host = host
        self._api_key = api_key
        self._item_id = int(item_id)
        self._func_id = int(func_id)
        self._timeout = int(timeout)

        self._attr_name = f"{name} Impuls"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-item-{self._item_id}-func-{self._func_id}-button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-item-{self._item_id}")},
            name=name,
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )

    async def async_press(self) -> None:
        session = async_get_clientsession(self.hass)
        url = f"{self._host}/api/item/executeItemFunction.json?api_key={self._api_key}"
        payload = {"id_item": self._item_id, "id_item_function": self._func_id}
        ok = await _post_ok(session, url, payload, self._timeout)
        if not ok:
            _LOGGER.warning("BernerBox: Impuls fehlgeschlagen (item=%s func=%s)", self._item_id, self._func_id)
            return
        entry_data = self.hass.data[DOMAIN][self._entry_id]
        coordinator = entry_data.get("coordinator")
        if coordinator is not None and hasattr(coordinator, "schedule_updateall"):
            for delay in (5, 25):
                coordinator.schedule_updateall(delay)
