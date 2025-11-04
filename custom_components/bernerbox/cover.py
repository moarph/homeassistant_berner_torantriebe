from __future__ import annotations

import logging
from typing import Optional, List, Dict

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    CoverDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .sensor import STATUS_MAP

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
        _LOGGER.debug("POST fail %s (%s)", url, e)
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
    coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")

    # 🔁 Sicherstellen, dass Namen verfügbar sind
    names: Dict[int, str] = hass.data[DOMAIN][entry.entry_id].get("names", {})
    if not names:
        _LOGGER.debug("BernerBox Cover: Lade Namen direkt aus API (Fallback)")
        url_list = f"{host}/api/item/getItemsByUser.json/{user_id}?api_key={api_key}"
        lst = await _get_json(session, url_list, timeout)
        if isinstance(lst, list):
            for it in lst:
                try:
                    iid = int(it.get("id_item"))
                    nm = str(it.get("name") or f"Item {iid}")
                    names[iid] = nm
                except Exception:
                    continue
        for iid in ids:
            names.setdefault(iid, f"Item {iid}")
        hass.data[DOMAIN][entry.entry_id]["names"] = names

    entities: List[BernerBoxGarageCover] = []
    for iid in ids:
        name = names.get(iid, f"Item {iid}")
        entities.append(
            BernerBoxGarageCover(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                host=host,
                api_key=api_key,
                item_id=iid,
                func_id=iid,
                timeout=timeout,
                display_name=name,
            )
        )

    async_add_entities(entities)
    _LOGGER.info("BernerBox: %d Garage-Cover(s) registriert", len(entities))


# ----------------------- Entity -----------------------------
class BernerBoxGarageCover(CoordinatorEntity, CoverEntity):
    """Garage Door (Cover) mit stabilem Namen & Status via Coordinator."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator,
        entry_id: str,
        host: str,
        api_key: str,
        item_id: int,
        func_id: int,
        timeout: int,
        display_name: str,
    ):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._host = host
        self._api_key = api_key
        self._item_id = int(item_id)
        self._func_id = int(func_id)
        self._timeout = int(timeout)

        self._attr_name = display_name  # ✅ stabiler Friendly Name
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-item-{self._item_id}-cover"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-item-{self._item_id}")},
            name=display_name,
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )

        self._last_is_closed: Optional[bool] = None

    # --------- Helper ----------
    @property
    def _entry(self) -> Optional[Dict]:
        data = getattr(self.coordinator, "data", None)
        if isinstance(data, dict):
            return data.get(str(self._item_id))
        return None

    def _derive_is_closed(self) -> Optional[bool]:
        entry = self._entry
        if not isinstance(entry, dict):
            return self._last_is_closed

        mc = entry.get("matchcode_item_type_status")
        raw = entry.get("id_item_type_status")
        state = None

        if isinstance(mc, str):
            state = STATUS_MAP.get(mc)
            if not state:
                mcl = mc.lower()
                if "zu" in mcl:
                    state = "closed"
                elif "auf" in mcl:
                    state = "open"
                elif "beweg" in mcl:
                    state = "moving"
                elif "fehler" in mcl or "error" in mcl:
                    state = "error"

        if not state and raw is not None:
            state = {"1": "open", "2": "closed", "3": "moving", "4": "error"}.get(str(raw))

        if state == "closed":
            return True
        if state == "open":
            return False
        return self._last_is_closed

    # --------- CoverEntity API ----------
    @property
    def is_closed(self) -> Optional[bool]:
        val = self._derive_is_closed()
        self._last_is_closed = val
        return val

    async def async_open_cover(self, **kwargs) -> None:
        await self._impulse_and_schedule_updates()

    async def async_close_cover(self, **kwargs) -> None:
        await self._impulse_and_schedule_updates()

    # --------- Impuls mit Nachlauf-Updates ----------
    async def _impulse_and_schedule_updates(self) -> None:
        session = async_get_clientsession(self.hass)
        url = f"{self._host}/api/item/executeItemFunction.json?api_key={self._api_key}"
        payload = {"id_item": self._item_id, "id_item_function": self._func_id}

        ok = await _post_ok(session, url, payload, self._timeout)
        if not ok:
            _LOGGER.warning("BernerBox: Impuls (Cover) fehlgeschlagen (item=%s func=%s)", self._item_id, self._func_id)
            return

        # updateAll nach 5s und 25s
        try:
            entry_data = self.hass.data[DOMAIN][self._entry_id]
            coordinator = entry_data.get("coordinator")
            if coordinator is not None and hasattr(coordinator, "schedule_updateall"):
                for delay in (5, 25):
                    coordinator.schedule_updateall(delay)
                _LOGGER.debug(
                    "BernerBox Cover: scheduled updateAll for item=%s at +5s and +25s",
                    self._item_id,
                )
        except Exception as e:
            _LOGGER.debug("BernerBox Cover: could not schedule updateAll: %s", e)
