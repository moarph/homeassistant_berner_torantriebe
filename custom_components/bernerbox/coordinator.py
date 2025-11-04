from __future__ import annotations
from datetime import timedelta
import asyncio
import logging
from typing import Dict, Any, Optional, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Ein gemeinsamer Poll alle X Sekunden (kannst du erhöhen, z.B. 10–15s)
SCAN_INTERVAL = timedelta(seconds=5)

async def _get_json(session, url: str, timeout: int) -> Optional[Any]:
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

class BernerBoxCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Ein Request-Paar pro Zyklus für alle Items (updateAllItemsByUser + getItemsByUser)."""

    def __init__(self, hass: HomeAssistant, *, host: str, api_key: str, user_id: int, timeout: int, ids: List[int]) -> None:
        super().__init__(hass, _LOGGER, name=f"BernerBox@{host}", update_interval=SCAN_INTERVAL)
        self._host = host.rstrip("/")
        self._api_key = api_key
        self._user_id = user_id
        self._timeout = timeout
        self._ids = [int(i) for i in ids]
        self._session = async_get_clientsession(hass)
        self.names: Dict[int, str] = {}  # stabile Namen (einmalig befüllt)

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        # 1) globales Refresh anstoßen
        await _get_json(self._session, f"{self._host}/api/item/updateAllItemsByUser.json/{self._user_id}?api_key={self._api_key}", self._timeout)

        # 2) kleine Pause (Box pollt intern je Item ~2s)
        await asyncio.sleep(2)

        # 3) Liste für alle Items holen
        data = await _get_json(self._session, f"{self._host}/api/item/getItemsByUser.json/{self._user_id}?api_key={self._api_key}", self._timeout)
        if not isinstance(data, list):
            raise UpdateFailed("getItemsByUser returned no list")

        # stabile Namen einmalig setzen
        if not self.names:
            for it in data:
                try:
                    iid = int(it.get("id_item"))
                    nm = (it.get("name") or f"Item {iid}").strip()
                    self.names[iid] = nm
                except Exception:
                    continue
            for iid in self._ids:
                self.names.setdefault(iid, f"Item {iid}")

        # nur konfigurierte IDs in ein Dict legen
        by_id: Dict[str, Dict[str, Any]] = {}
        for it in data:
            iid = it.get("id_item")
            if iid and int(iid) in self._ids:
                by_id[str(iid)] = it
        return by_id

async def async_get_coordinator(hass: HomeAssistant, entry_id: str) -> BernerBoxCoordinator:
    """Factory: liefert den Coordinator, erzeugt ihn bei Bedarf einmalig."""
    box_state = hass.data[DOMAIN][entry_id]
    coord = box_state.get("coordinator")
    if coord:
        return coord

    host = box_state["host"]
    api_key = box_state["api_key"]
    timeout = int(box_state.get("request_timeout", 6))
    user_id = int(box_state.get("user_id", 1))
    ids: List[int] = list(map(int, box_state.get("ids", []))) or list(range(1, 21))

    coord = BernerBoxCoordinator(hass, host=host, api_key=api_key, user_id=user_id, timeout=timeout, ids=ids)
    box_state["coordinator"] = coord
    await coord.async_config_entry_first_refresh()
    return coord
