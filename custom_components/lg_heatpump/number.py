"""Number platform for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUMBER_TYPES, ModbusNumberDescription
from .coordinator import LgHeatpumpModbusCoordinator
from .modbus_compat import get_pymodbus_device_param

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    key_to_coordinator: dict[str, LgHeatpumpModbusCoordinator] = data["key_to_coordinator"]
    client = data["client"]
    slave = data["slave"]

    entities = [
        LgHeatpumpNumber(
            key_to_coordinator[description.source_key], client, slave, description, entry
        )
        for description in NUMBER_TYPES
    ]
    async_add_entities(entities)


class LgHeatpumpNumber(CoordinatorEntity[LgHeatpumpModbusCoordinator], NumberEntity):
    """A number entity backed by a source register (read) and a write address.

    The source register is read (and scaled) exactly like its matching
    sensor entity. On write, the displayed value is converted back to a
    raw register value using `write_scale`, and - if `signed` is set -
    encoded as a 16-bit two's complement value, mirroring the
    `set_value` templates in the original YAML.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LgHeatpumpModbusCoordinator,
        client: Any,
        slave: int,
        description: ModbusNumberDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._slave = slave
        self._description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit_of_measurement
        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="LG",
            model="Heatpump (Modbus)",
        )

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._description.source_key)

    async def async_set_native_value(self, value: float) -> None:
        raw = round(value * self._description.write_scale)
        if self._description.signed and raw < 0:
            raw += 0x10000
        raw = max(0, min(raw, 0xFFFF))

        result = await self._client.write_register(
            address=self._description.write_address,
            value=raw,
            **{get_pymodbus_device_param(): self._slave},
        )
        if result.isError():
            _LOGGER.error(
                "Failed writing %s (raw %s) to holding register %s (%s)",
                value,
                raw,
                self._description.write_address,
                self._description.key,
            )
            return
        await self.coordinator.async_request_refresh()
