"""Sensor platform for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES, ModbusSensorDescription
from .coordinator import LgHeatpumpModbusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    key_to_coordinator: dict[str, LgHeatpumpModbusCoordinator] = data["key_to_coordinator"]

    entities = [
        LgHeatpumpSensor(key_to_coordinator[description.key], description, entry)
        for description in SENSOR_TYPES
        if description.create_entity
    ]
    async_add_entities(entities)


class LgHeatpumpSensor(CoordinatorEntity[LgHeatpumpModbusCoordinator], SensorEntity):
    """Representation of a single Modbus register as a sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LgHeatpumpModbusCoordinator,
        description: ModbusSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="LG",
            model="Heatpump (Modbus)",
        )

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._description.key)
