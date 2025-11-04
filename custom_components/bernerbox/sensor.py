from __future__ import annotations

from datetime import timedelta
import asyncio
import logging
from time import time
from typing import Dict, Any, Optional, List

from aiohttp import ClientTimeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)

DOMAIN = "bernerbox"

_LOGGER = logging.getLogger(__name__)

# 🔁 App-ähnliches Verhalten:
SCAN_INTERVAL = timedelta(seconds=30)   # getItems alle 30s
UPDATEALL_SAFETY_INTERVAL = 300        # zusätzlicher Refresh alle 5 Minuten
POST_IMPULSE_DELAYS = (5, 25)          # +5s und +25s nach Button

# Mappings für Statusableitung
STATUS_MAP = {
    "item_type_status_zu": "closed",
    "item_type_status_auf": "open",
    "item_type_status_in_bewegung": "moving",
    "item_type_status_fehlfunktion": "error",
}
NUM_STATUS_MAP = {"1": "open", "2": "closed", "3": "moving", "4": "error"}
TEXT_FALLBACK = {"zu": "closed", "auf": "open", "beweg": "moving", "error": "error", "fehler": "error"}


async def _get_json(session, url: str, timeout: int) -> Optional[Any]:
    """HTTP-GET als JSON (fehlertolerant)."""
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


async def _fire_and_forget_get(session, url: str) -> None:
    """Startet einen GET ohne Coordinator zu blockieren (kein Gesamt-Timeout)."""
    try:
        async with session.get(url, timeout=ClientTimeout(total=None), headers={"Accept": "application/json"}) as resp:
            await resp.read()
    except Exception as e:
        _LOGGER.debug("updateAll fire-and-forget error: %s", e)


class BernerBoxCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """
    Koordiniert Polling & Update-Plan:
    - getItemsByUser: alle 30s
    - updateAllItemsByUser: planbar (+5s/+25s nach Impuls) + Sicherheitslauf alle 5min
    - niemals UpdateFailed werfen → alte Daten bleiben erhalten
    """

    def __init__(self, hass: HomeAssistant, *, host: str, api_key: str, user_id: int, timeout: int, ids: List[int]) -> None:
        super().__init__(hass, _LOGGER, name=f"BernerBox@{host}", update_interval=SCAN_INTERVAL)
        self._host = host.rstrip("/")
        self._api_key = api_key
        self._user_id = user_id
        self._timeout = max(int(timeout), 10)
        self._ids = [int(i) for i in ids]
        self._session = async_get_clientsession(hass)

        # Stabile Namen einmalig merken; werden nie überschrieben
        self.names: Dict[int, str] = {}

        # Zeitmanagement
        self.last_seen: float | None = None        # erfolgreiche Liste
        self._last_updateall: float = 0.0          # letzter Sicherheitslauf
        self._due_updates: List[float] = []        # geplante updateAll-Zeitpunkte (epoch)

    # ——— Planer-API: vom Button nutzbar ———
    def schedule_updateall(self, delay_s: int) -> None:
        ts = time() + max(0, int(delay_s))
        self._due_updates.append(ts)
        # doppelte/alte Termine aufräumen
        now = time()
        self._due_updates = sorted(t for t in self._due_updates if t >= now - 1)
        _LOGGER.debug("BernerBoxCoordinator: scheduled updateAll at %s (queue=%s)", int(ts), [int(t) for t in self._due_updates])

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Zentraler Update-Zyklus: ggf. updateAll starten, dann Liste holen."""
        now = time()
        url_update = f"{self._host}/api/item/updateAllItemsByUser.json/{self._user_id}?api_key={self._api_key}"
        url_list   = f"{self._host}/api/item/getItemsByUser.json/{self._user_id}?api_key={self._api_key}"

        # 1) updateAll anstoßen, wenn fällig: geplante Termine oder 5-Min-Sicherheit
        should_update = False
        if self._due_updates and self._due_updates[0] <= now:
            should_update = True
            self._due_updates.pop(0)
        elif now - self._last_updateall >= UPDATEALL_SAFETY_INTERVAL:
            should_update = True

        if should_update:
            _LOGGER.debug("BernerBoxCoordinator: calling updateAll (fire-and-forget) -> %s", url_update)
            self.hass.async_create_task(_fire_and_forget_get(self._session, url_update))
            self._last_updateall = now
            await asyncio.sleep(3.5)  # Box kurz „Luft“ lassen

        # 2) Liste holen (Hauptquelle für Zustände)
        data = await _get_json(self._session, url_list, self._timeout)
        if isinstance(data, list):
            self.last_seen = time()
        else:
            _LOGGER.warning("BernerBoxCoordinator: list not a list -> %r", data)
            return self.data or {}

        # 3) Namen beim ersten Mal füllen
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

        # 4) Nur konfigurierte IDs in Dict packen
        by_id: Dict[str, Dict[str, Any]] = {}
        for it in data:
            iid = it.get("id_item")
            if iid is None:
                continue
            try:
                iidi = int(iid)
            except Exception:
                continue
            if iidi in self._ids:
                by_id[str(iidi)] = it

        _LOGGER.debug("BernerBoxCoordinator: fetched keys=%s (configured=%s)", sorted(by_id.keys()), self._ids)
        return by_id


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    host: str = data["host"].rstrip("/")
    api_key: str = data["api_key"]
    timeout: int = int(data.get("request_timeout", 6))
    user_id: int = int(data.get("user_id", 1))
    ids: List[int] = list(map(int, data.get("ids", []))) or list(range(1, 21))

    coordinator = BernerBoxCoordinator(
        hass, host=host, api_key=api_key, user_id=user_id, timeout=timeout, ids=ids
    )
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await coordinator.async_config_entry_first_refresh()

    entities: List[BernerBoxItemStateSensor] = []
    for iid in ids:
        name = coordinator.names.get(iid, f"Item {iid}")
        entities.append(
            BernerBoxItemStateSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                item_id=iid,
                display_name=f"{name} Status",
                base_name=name,
            )
        )

    async_add_entities(entities)
    _LOGGER.info(
        "BernerBox: %d Status-Sensor(en) registriert (User %s, getItems %ss, updateAll: +5/+25s nach Impuls & alle 300s)",
        len(entities), user_id, int(SCAN_INTERVAL.total_seconds())
    )


class BernerBoxItemStateSensor(CoordinatorEntity[BernerBoxCoordinator], SensorEntity):
    """Status eines Items aus dem gemeinsamen Coordinator (kein eigener HTTP-Poll)."""

    _attr_should_poll = False
    _attr_icon = "mdi:garage"

    def __init__(self, *, coordinator: BernerBoxCoordinator, entry_id: str, item_id: int, display_name: str, base_name: str):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._item_id = int(item_id)

        self._attr_name = display_name
        self._base_name = base_name

        self._attr_unique_id = f"{DOMAIN}-{entry_id}-item-{self._item_id}-status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-item-{self._item_id}")},
            name=self._base_name,
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )

        self._last_state: Optional[str] = None
        self._attr_native_value = None
        self._attr_extra_state_attributes = {
            "last_seen": None,
            "last_seen_age": None,
            "reachable": None,
            "matchcode_item_type_status": None,
            "matchcode_item_type_torlage": None,
            "matchcode_item_type_error": None,
            "id_item_type_status": None,
            "id_item_type_torlage": None,
            "id_item_type_error": None,
            "timestamp_executed": None,
            "raw_source": "getItemsByUser (coordinated)",
        }

    @property
    def _entry(self) -> Optional[Dict[str, Any]]:
        if not isinstance(self.coordinator.data, dict):
            return None
        return self.coordinator.data.get(str(self._item_id))

    def _derive_state(self, entry: Dict[str, Any]) -> Optional[str]:
        mc = entry.get("matchcode_item_type_status")
        if isinstance(mc, str):
            st = STATUS_MAP.get(mc)
            if st:
                return st
            mcl = mc.lower()
            for key, val in TEXT_FALLBACK.items():
                if key in mcl:
                    return val
        raw_id = entry.get("id_item_type_status")
        if raw_id is not None:
            st = NUM_STATUS_MAP.get(str(raw_id))
            if st:
                return st
        return None

    def _update_from_entry(self, entry: Dict[str, Any]) -> None:
        # „Frische“ der Liste anzeigen
        ls = getattr(self.coordinator, "last_seen", None)
        age = None
        if isinstance(ls, (int, float)):
            age = max(0, int(time() - ls))
        self._attr_extra_state_attributes["last_seen"] = ls
        self._attr_extra_state_attributes["last_seen_age"] = age

        # Rohattribute übernehmen
        self._attr_extra_state_attributes.update({
            "reachable": True,
            "matchcode_item_type_status": entry.get("matchcode_item_type_status"),
            "matchcode_item_type_torlage": entry.get("matchcode_item_type_torlage"),
            "matchcode_item_type_error": entry.get("matchcode_item_type_error"),
            "id_item_type_status": entry.get("id_item_type_status"),
            "id_item_type_torlage": entry.get("id_item_type_torlage"),
            "id_item_type_error": entry.get("id_item_type_error"),
            "timestamp_executed": entry.get("timestamp_executed"),
        })

        new_state = self._derive_state(entry)
        if new_state:
            self._attr_native_value = new_state
            self._last_state = new_state
        else:
            self._attr_native_value = self._last_state or "unknown"

    def _handle_coordinator_update(self) -> None:
        entry = self._entry
        if isinstance(entry, dict):
            self._update_from_entry(entry)
            _LOGGER.debug(
                "BernerBoxSensor[%s]: updated -> state=%s mc=%r raw=%r ts=%r",
                self._item_id,
                self._attr_native_value,
                entry.get("matchcode_item_type_status"),
                entry.get("id_item_type_status"),
                entry.get("timestamp_executed"),
            )
        else:
            self._attr_extra_state_attributes["reachable"] = True
            self._attr_native_value = self._last_state or "unknown"
            _LOGGER.debug(
                "BernerBoxSensor[%s]: entry missing; available keys=%s",
                self._item_id,
                sorted(list(self.coordinator.data.keys())) if isinstance(self.coordinator.data, dict) else type(self.coordinator.data),
            )
        super()._handle_coordinator_update()
