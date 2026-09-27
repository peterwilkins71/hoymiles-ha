from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfMass, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from . import HoymilesConfigEntry
from .const import CONF_STATION_ID, CONF_STATION_NAME, DOMAIN


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class HoymilesSensorDescription(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]


def _power(key: str, name: str) -> HoymilesSensorDescription:
    return HoymilesSensorDescription(
        key=f"live_{key}", name=name,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d, k=key: _num((d.get("power") or {}).get(k)),
    )


def _energy(key: str, name: str, total: bool = False) -> HoymilesSensorDescription:
    # The API reports energy in Wh.
    return HoymilesSensorDescription(
        key=key, name=name,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda d, k=key: _num(d.get(k)),
    )


LIVE_SENSORS = (
    _power("pv", "Solar power"),
    _power("load", "Load power"),
    _power("grid", "Grid power"),
    _power("bat", "Battery power"),
    HoymilesSensorDescription(
        key="live_pvr", name="Solar output of capacity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: _num((d.get("power") or {}).get("pvr")),
    ),
)

TOTAL_SENSORS = (
    _energy("today_eq", "Energy today"),
    _energy("month_eq", "Energy this month"),
    _energy("year_eq", "Energy this year"),
    _energy("total_eq", "Energy total"),
    HoymilesSensorDescription(
        key="real_power", name="Reported power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: _num(d.get("real_power")),
    ),
    HoymilesSensorDescription(
        key="co2_emission_reduction", name="CO2 avoided",
        # Tracks total_eq at ~1 g/Wh, so the figure is in grams.
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value=lambda d: _num(d.get("co2_emission_reduction")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: HoymilesConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    sid = entry.data[CONF_STATION_ID]
    device = DeviceInfo(
        identifiers={(DOMAIN, str(sid))},
        name=entry.data.get(CONF_STATION_NAME) or f"Hoymiles {sid}",
        manufacturer="Hoymiles",
        model="S-Miles Cloud station",
    )
    async_add_entities(
        [HoymilesSensor(data.live, d, sid, device) for d in LIVE_SENSORS]
        + [HoymilesSensor(data.totals, d, sid, device) for d in TOTAL_SENSORS]
    )


class HoymilesSensor(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity):
    entity_description: HoymilesSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description: HoymilesSensorDescription, sid: int, device: DeviceInfo) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{sid}_{description.key}"
        self._attr_device_info = device

    @property
    def native_value(self):
        return self.entity_description.value(self.coordinator.data or {})
