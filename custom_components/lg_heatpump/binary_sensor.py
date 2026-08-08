"""Binary sensor platform for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_TYPES, DOMAIN, ModbusBinarySensorDescription
from .coordinator import LgHeatpumpModbusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    key_to_coordinator: dict[str, LgHeatpumpModbusCoordinator] = data["key_to_coordinator"]

    entities = [
        LgHeatpumpBinarySensor(key_to_coordinator[description.key], description, entry)
        for description in BINARY_SENSOR_TYPES
    ]
    async_add_entities(entities)


class LgHeatpumpBinarySensor(CoordinatorEntity[LgHeatpumpModbusCoordinator], BinarySensorEntity):
    """Representation of a discrete_input register as a binary_sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LgHeatpumpModbusCoordinator,
        description: ModbusBinarySensorDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="LG",
            model="Heatpump (Modbus)",
        )

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self._description.key)
        if value is None:
            return None
        return bool(value)
