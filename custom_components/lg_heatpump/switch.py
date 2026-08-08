"""Switch platform for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_TYPES, ModbusSwitchDescription
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
        LgHeatpumpSwitch(key_to_coordinator[description.key], client, slave, description, entry)
        for description in SWITCH_TYPES
    ]
    async_add_entities(entities)


class LgHeatpumpSwitch(CoordinatorEntity[LgHeatpumpModbusCoordinator], SwitchEntity):
    """Representation of a writable coil as a switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LgHeatpumpModbusCoordinator,
        client: Any,
        slave: int,
        description: ModbusSwitchDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._slave = slave
        self._description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(False)

    async def _write(self, value: bool) -> None:
        result = await self._client.write_coil(
            address=self._description.write_address,
            value=value,
            **{get_pymodbus_device_param(): self._slave},
        )
        if result.isError():
            _LOGGER.error(
                "Failed writing coil %s (%s) to %s",
                self._description.write_address,
                self._description.key,
                value,
            )
            return
        await self.coordinator.async_request_refresh()
