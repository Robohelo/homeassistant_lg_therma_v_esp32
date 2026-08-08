"""The LG Heatpump (Modbus) integration."""
from __future__ import annotations

import logging
from collections import defaultdict

from pymodbus.client import AsyncModbusTcpClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    BINARY_SENSOR_TYPES,
    CONF_SLAVE,
    DOMAIN,
    INPUT_TYPE_COIL,
    INPUT_TYPE_DISCRETE,
    PLATFORMS,
    SENSOR_TYPES,
    SWITCH_TYPES,
    ModbusSensorDescription,
)
from .coordinator import LgHeatpumpModbusCoordinator

_LOGGER = logging.getLogger(__name__)


def _binary_sensor_read_descriptions() -> list[ModbusSensorDescription]:
    """Turn binary_sensor descriptions into readable register descriptions."""
    return [
        ModbusSensorDescription(
            key=b.key,
            name=b.name,
            address=b.address,
            input_type=INPUT_TYPE_DISCRETE,
            scan_interval=b.scan_interval,
        )
        for b in BINARY_SENSOR_TYPES
    ]


def _switch_verify_descriptions() -> list[ModbusSensorDescription]:
    """Turn switch verify-addresses into readable register descriptions."""
    return [
        ModbusSensorDescription(
            key=s.key,
            name=s.name,
            address=s.verify_address,
            input_type=INPUT_TYPE_COIL,
            scan_interval=s.scan_interval,
        )
        for s in SWITCH_TYPES
    ]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG Heatpump (Modbus) from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    slave = entry.data[CONF_SLAVE]

    client = AsyncModbusTcpClient(host=host, port=port)
    if not await client.connect():
        raise ConfigEntryNotReady(f"Unable to connect to Modbus device at {host}:{port}")

    # Every readable register across all platforms (sensor, binary_sensor,
    # switch state read-back) is grouped into shared coordinators by
    # scan_interval, so registers that poll at the same rate share one
    # coordinator/request cycle instead of hammering the gateway with
    # separate concurrent pollers.
    all_read_descriptions: list[ModbusSensorDescription] = [
        *SENSOR_TYPES,
        *_binary_sensor_read_descriptions(),
        *_switch_verify_descriptions(),
    ]

    groups: dict[int, list[ModbusSensorDescription]] = defaultdict(list)
    for description in all_read_descriptions:
        groups[description.scan_interval].append(description)

    coordinators: list[LgHeatpumpModbusCoordinator] = []
    key_to_coordinator: dict[str, LgHeatpumpModbusCoordinator] = {}
    for interval, descriptions in groups.items():
        coordinator = LgHeatpumpModbusCoordinator(hass, client, slave, descriptions, interval)
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)
        for description in descriptions:
            key_to_coordinator[description.key] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "slave": slave,
        "coordinators": coordinators,
        "key_to_coordinator": key_to_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options/config change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()
    return unload_ok
