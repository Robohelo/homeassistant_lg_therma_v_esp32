"""Config flow for the LG Heatpump (Modbus) integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from pymodbus.client import AsyncModbusTcpClient

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_SLAVE, DEFAULT_PORT, DEFAULT_SLAVE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE): int,
    }
)


async def _test_connection(host: str, port: int) -> bool:
    """Try to open and close a Modbus TCP connection to validate host/port."""
    client = AsyncModbusTcpClient(host=host, port=port)
    try:
        return await client.connect()
    finally:
        await client.close()


class LgHeatpumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Heatpump (Modbus)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_SLAVE]}"
            )
            self._abort_if_unique_id_configured()

            try:
                connected = await _test_connection(user_input[CONF_HOST], user_input[CONF_PORT])
            except Exception:  # noqa: BLE001 - defensive, surfaced as a form error
                _LOGGER.exception("Unexpected error testing Modbus connection")
                errors["base"] = "unknown"
            else:
                if not connected:
                    errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=f"LG Heatpump ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
