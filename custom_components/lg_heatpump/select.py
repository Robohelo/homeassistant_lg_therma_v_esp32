"""Select platform for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SELECT_TYPES, ModbusSelectDescription
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
        LgHeatpumpSelect(
            key_to_coordinator[description.source_key], client, slave, description, entry
        )
        for description in SELECT_TYPES
    ]
    async_add_entities(entities)


class LgHeatpumpSelect(CoordinatorEntity[LgHeatpumpModbusCoordinator], SelectEntity):
    """A select entity backed by a source register (read) and a write address."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LgHeatpumpModbusCoordinator,
        client: Any,
        slave: int,
        description: ModbusSelectDescription,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._slave = slave
        self._description = description
        self._value_to_option = {v: k for k, v in description.options.items()}
        self._attr_name = description.name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_options = list(description.options.keys())
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="LG",
            model="Heatpump (Modbus)",
        )

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return self._description.default_option or None
        raw = self.coordinator.data.get(self._description.source_key)
        if raw is None:
            return self._description.default_option or None
        return self._value_to_option.get(int(raw), self._description.default_option or None)

    async def async_select_option(self, option: str) -> None:
        if option not in self._description.options:
            _LOGGER.error("Unknown option %s for %s", option, self._description.key)
            return
        raw_value = self._description.options[option]
        result = await self._client.write_register(
            address=self._description.write_address,
            value=raw_value,
            **{get_pymodbus_device_param(): self._slave},
        )
        if result.isError():
            _LOGGER.error(
                "Failed writing %s to holding register %s (%s)",
                raw_value,
                self._description.write_address,
                self._description.key,
            )
            return
        await self.coordinator.async_request_refresh()
