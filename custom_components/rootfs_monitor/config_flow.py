"""Config flow for RootFS Monitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_CRIT_PERCENT,
    CONF_HOST_ROOT,
    CONF_SCAN_INTERVAL,
    CONF_TOP_N,
    CONF_WARN_PERCENT,
    DEFAULT_CRIT_PERCENT,
    DEFAULT_HOST_ROOT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_TOP_N,
    DEFAULT_WARN_PERCENT,
    DOMAIN,
    MAX_TOP_N,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)


class RootFSMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RootFS Monitor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle first step."""
        if user_input is not None:
            await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_HOST_ROOT]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="RootFS Monitor", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST_ROOT, default=DEFAULT_HOST_ROOT): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=DEFAULT_SCAN_INTERVAL_SECONDS,
                    ): vol.All(
                        int,
                        vol.Range(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                        ),
                    ),
                    vol.Required(CONF_TOP_N, default=DEFAULT_TOP_N): vol.All(
                        int,
                        vol.Range(min=1, max=MAX_TOP_N),
                    ),
                    vol.Required(CONF_WARN_PERCENT, default=DEFAULT_WARN_PERCENT): vol.All(
                        int,
                        vol.Range(min=1, max=100),
                    ),
                    vol.Required(CONF_CRIT_PERCENT, default=DEFAULT_CRIT_PERCENT): vol.All(
                        int,
                        vol.Range(min=1, max=100),
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get options flow for this handler."""
        return RootFSMonitorOptionsFlow(config_entry)


class RootFSMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.options or self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                    ): vol.All(
                        int,
                        vol.Range(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                        ),
                    ),
                    vol.Required(
                        CONF_TOP_N,
                        default=data.get(CONF_TOP_N, DEFAULT_TOP_N),
                    ): vol.All(int, vol.Range(min=1, max=MAX_TOP_N)),
                    vol.Required(
                        CONF_WARN_PERCENT,
                        default=data.get(CONF_WARN_PERCENT, DEFAULT_WARN_PERCENT),
                    ): vol.All(int, vol.Range(min=1, max=100)),
                    vol.Required(
                        CONF_CRIT_PERCENT,
                        default=data.get(CONF_CRIT_PERCENT, DEFAULT_CRIT_PERCENT),
                    ): vol.All(int, vol.Range(min=1, max=100)),
                }
            ),
        )
