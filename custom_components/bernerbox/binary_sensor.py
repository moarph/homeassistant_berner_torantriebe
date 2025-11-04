from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import async_get_coordinator, BernerBoxCoordinator
from .sensor import STATUS_MAP, NUM_STATUS_MAP, TEXT_FALLBACK

_LOGGER = logging.getLogger(__name__)

GARAGE_ITEM_TYPES = {"1", "2"}  # aus Backend: 1 vertikal, 2 horizontal

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coord: BernerBoxCoordinator = await async_get_coordinator(hass, entry.entry_id)
    ids: List[int] = list(map(int, hass.data[DOMAIN][entry.entry_id].get("ids", []))) or list(range(1, 21))
    entities: List[BernerBoxDoorBinarySensor] = []
    for iid in ids:
        name = coord.names.get(iid, f"Item {iid}")
        entities.append(
            BernerBoxDoorBinarySensor(
                coordinator=coord,
                entry_id=entry.entry_id,
                item_id=iid,
                display_name=f"{name} Türstatus",
                base_name=name,
            )
        )
    async_add_entities(entities)

class BernerBoxDoorBinarySensor(CoordinatorEntity[BernerBoxCoordinator], BinarySensorEntity):
    """device_class garage_door/door → zeigt „geöffnet/geschlossen“ lokalisiert; hält letzten guten Zustand."""

    _attr_should_poll = False

    def __init__(self, *, coordinator: BernerBoxCoordinator, entry_id: str, item_id: int, display_name: str, base_name: str):
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._item_id = int(item_id)
        self._attr_name = display_name
        self._base_name = base_name
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-item-{self._item_id}-door"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}-item-{self._item_id}")},
            name=self._base_name,
            manufacturer="Berner Torantriebe KG",
            model="BERNER-BOX",
        )
        # Device-Class anhand des Item-Typs
        item_type = (self._entry or {}).get("id_item_type")
        self._attr_device_class = "garage_door" if str(item_type) in GARAGE_ITEM_TYPES else "door"
        self._last_is_on: Optional[bool] = None
        self._attr_extra_state_attributes = {
            "reachable": None,
            "matchcode_item_type_status": None,
            "id_item_type_status": None,
            "timestamp_executed": None,
            "raw_source": "getItemsByUser (coordinated)",
        }

    @property
    def _entry(self) -> Optional[Dict[str, Any]]:
        return self.coordinator.data.get(str(self._item_id)) if isinstance(self.coordinator.data, dict) else None

    def _derive_is_on(self, entry: Dict[str, Any]) -> Optional[bool]:
        mc = entry.get("matchcode_item_type_status")
        if isinstance(mc, str):
            st = STATUS_MAP.get(mc)
            if not st:
                mcl = mc.lower()
                for key, val in TEXT_FALLBACK.items():
                    if key in mcl:
                        st = val
                        break
            if st == "open":
                return True
            if st == "closed":
                return False
            return None
        raw_id = entry.get("id_item_type_status")
        if raw_id is not None:
            st = NUM_STATUS_MAP.get(str(raw_id))
            if st == "open":
                return True
            if st == "closed":
                return False
        return None

    def _handle_coordinator_update(self) -> None:
        entry = self._entry
        if isinstance(entry, dict):
            self._attr_extra_state_attributes.update({
                "reachable": True,
                "matchcode_item_type_status": entry.get("matchcode_item_type_status"),
                "id_item_type_status": entry.get("id_item_type_status"),
                "timestamp_executed": entry.get("timestamp_executed"),
            })
            # Device-Class ggf. einmalig nachziehen
            it = entry.get("id_item_type")
            if not self.device_class and it is not None:
                self._attr_device_class = "garage_door" if str(it) in GARAGE_ITEM_TYPES else "door"

            new_is_on = self._derive_is_on(entry)
            if new_is_on is not None:
                self._attr_is_on = new_is_on
                self._last_is_on = new_is_on
            else:
                self._attr_is_on = self._last_is_on  # unverändert lassen
        else:
            self._attr_extra_state_attributes["reachable"] = False
            self._attr_is_on = self._last_is_on  # unverändert lassen
        super()._handle_coordinator_update()
