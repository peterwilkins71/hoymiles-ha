from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HoymilesConfigEntry
from .const import CONF_STATION_ID, PRODUCING_THRESHOLD_W
from .coordinator import LiveCoordinator
from .sensor import station_device


async def async_setup_entry(
    hass: HomeAssistant, entry: HoymilesConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ProducingSensor(entry.runtime_data.live, entry)])


class ProducingSensor(CoordinatorEntity[LiveCoordinator], BinarySensorEntity):
    """On while the panels are producing; gives cards an on/off state to colour."""

    _attr_has_entity_name = True
    _attr_name = "Producing"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator: LiveCoordinator, entry: HoymilesConfigEntry) -> None:
        super().__init__(coordinator)
        sid = entry.data[CONF_STATION_ID]
        self._attr_unique_id = f"{sid}_producing"
        self._attr_device_info = station_device(entry)

    @property
    def available(self) -> bool:
        # No live data (e.g. the inverter is off overnight) reads as "not producing"
        # rather than unavailable, so cards keyed on this state keep working.
        return True

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.last_update_success:
            return False
        power = (self.coordinator.data or {}).get("power") or {}
        try:
            return float(power.get("pv")) > PRODUCING_THRESHOLD_W
        except (TypeError, ValueError):
            return None

    @property
    def icon(self) -> str:
        return "mdi:solar-power" if self.is_on else "mdi:solar-power-variant-outline"
