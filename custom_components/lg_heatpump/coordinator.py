"""DataUpdateCoordinator for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_TYPE_FLOAT32,
    DATA_TYPE_INT16,
    DATA_TYPE_INT32,
    DATA_TYPE_UINT32,
    DOMAIN,
    INPUT_TYPE_COIL,
    INPUT_TYPE_DISCRETE,
    INPUT_TYPE_HOLDING,
    INPUT_TYPE_INPUT,
    ModbusSensorDescription,
)
from .modbus_compat import get_pymodbus_device_param

_LOGGER = logging.getLogger(__name__)

_32BIT_FORMATS = {
    DATA_TYPE_UINT32: ">I",
    DATA_TYPE_INT32: ">i",
    DATA_TYPE_FLOAT32: ">f",
}


def _decode_registers(registers: list[int], description: ModbusSensorDescription) -> float | int:
    """Decode raw register words according to the sensor's data_type."""
    data_type = description.data_type

    if data_type == DATA_TYPE_INT16:
        value: float | int = registers[0]
        if value > 0x7FFF:
            value -= 0x10000
    elif data_type in _32BIT_FORMATS:
        raw = struct.pack(">HH", registers[0], registers[1])
        value = struct.unpack(_32BIT_FORMATS[data_type], raw)[0]
    else:
        # uint16 / raw coil-bit / default
        value = registers[0]

    value = value * description.scale + description.offset
    if description.precision is not None:
        value = round(value, description.precision)
    return value


class LgHeatpumpModbusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls a group of Modbus registers that all share a scan_interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Any,
        slave: int,
        sensors: list[ModbusSensorDescription],
        update_interval: int,
        lock: asyncio.Lock,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{update_interval}s",
            update_interval=timedelta(seconds=update_interval),
        )
        self.client = client
        self.slave = slave
        self.sensors = sensors
        self.lock = lock

    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for description in self.sensors:
            try:
                data[description.key] = await self._read_one(description)
            except Exception as err:  # noqa: BLE001 - log and continue polling others
                _LOGGER.debug(
                    "Error reading %s (address %s): %s",
                    description.key,
                    description.address,
                    err,
                )
                data[description.key] = None
        return data

    async def _read_one(self, description: ModbusSensorDescription) -> float | int | None:
        # pymodbus 3.10+ renamed `slave=` to `device_id=` (and dropped the
        # old name entirely); pymodbus 3.8+ also made `count` keyword-only.
        # See modbus_compat.py for why this can't just be pinned in
        # manifest.json - HA resolves one shared pymodbus version for
        # every integration.
        kwargs = {
            "address": description.address,
            "count": description.count,
            get_pymodbus_device_param(): self.slave,
        }

        if description.input_type == INPUT_TYPE_INPUT:
            method = self.client.read_input_registers
        elif description.input_type == INPUT_TYPE_HOLDING:
            method = self.client.read_holding_registers
        elif description.input_type == INPUT_TYPE_COIL:
            method = self.client.read_coils
        elif description.input_type == INPUT_TYPE_DISCRETE:
            method = self.client.read_discrete_inputs
        else:
            raise UpdateFailed(f"Unsupported input_type: {description.input_type}")

        # Serialize every request/response exchange through the shared lock -
        # see the comment in __init__.py's async_setup_entry for why this
        # isn't optional on a transparent RS-485<->TCP gateway.
        async with self.lock:
            result = await method(**kwargs)

        if result.isError():
            raise UpdateFailed(f"Modbus error reading {description.key}: {result}")

        registers = getattr(result, "registers", None)
        if registers is None:
            registers = getattr(result, "bits", None)
        if registers is None:
            raise UpdateFailed(f"No data returned for {description.key}")

        return _decode_registers(list(registers), description)
