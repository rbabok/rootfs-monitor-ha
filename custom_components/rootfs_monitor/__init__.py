"""RootFS monitor integration setup."""

from __future__ import annotations

from collections.abc import Mapping

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .cleanup import (
    run_apt_cache_cleanup,
    run_docker_cleanup,
    run_journald_cleanup,
    run_var_log_cleanup,
)
from .const import (
    ATTR_ALL_IMAGES,
    ATTR_DRY_RUN,
    ATTR_INCLUDE_VOLUMES,
    ATTR_MIN_AGE_DAYS,
    ATTR_MODE,
    ATTR_UNTIL,
    ATTR_VACUUM_SIZE,
    ATTR_VACUUM_TIME,
    DOMAIN,
    MODE_AUTOCLEAN,
    MODE_CLEAN,
    PLATFORMS,
    SERVICE_CLEANUP_APT_CACHE,
    SERVICE_CLEANUP_DOCKER,
    SERVICE_CLEANUP_JOURNALD,
    SERVICE_CLEANUP_VAR_LOG,
)
from .coordinator import RootFSDataUpdateCoordinator

SERVICE_SCHEMA_CLEANUP_DOCKER = vol.Schema(
    {
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
        vol.Optional(ATTR_ALL_IMAGES, default=False): cv.boolean,
        vol.Optional(ATTR_INCLUDE_VOLUMES, default=False): cv.boolean,
        vol.Optional(ATTR_UNTIL): cv.string,
    }
)

SERVICE_SCHEMA_CLEANUP_JOURNALD = vol.Schema(
    {
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
        vol.Optional(ATTR_VACUUM_SIZE): cv.string,
        vol.Optional(ATTR_VACUUM_TIME): cv.string,
    }
)

SERVICE_SCHEMA_CLEANUP_APT = vol.Schema(
    {
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
        vol.Optional(ATTR_MODE, default=MODE_AUTOCLEAN): vol.In([MODE_AUTOCLEAN, MODE_CLEAN]),
    }
)

SERVICE_SCHEMA_CLEANUP_VAR_LOG = vol.Schema(
    {
        vol.Optional(ATTR_DRY_RUN, default=True): cv.boolean,
        vol.Optional(ATTR_MIN_AGE_DAYS, default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RootFS Monitor integration from YAML (unused)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RootFS monitor from a config entry."""
    coordinator = RootFSDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, SERVICE_CLEANUP_DOCKER):
        _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            _unregister_services(hass)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register cleanup services."""

    async def _service_runner(
        call: ServiceCall,
        runner,
    ) -> None:
        coordinator = _get_first_coordinator(hass)
        if coordinator is None:
            return

        result = await runner(
            hass=hass,
            host_root=coordinator.host_root,
            payload=call.data,
        )
        coordinator.set_last_cleanup(result)
        await coordinator.async_request_refresh()

    async def _cleanup_docker(call: ServiceCall) -> None:
        await _service_runner(call, run_docker_cleanup)

    async def _cleanup_journald(call: ServiceCall) -> None:
        await _service_runner(call, run_journald_cleanup)

    async def _cleanup_apt(call: ServiceCall) -> None:
        await _service_runner(call, run_apt_cache_cleanup)

    async def _cleanup_var_log(call: ServiceCall) -> None:
        await _service_runner(call, run_var_log_cleanup)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_DOCKER,
        _cleanup_docker,
        schema=SERVICE_SCHEMA_CLEANUP_DOCKER,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_JOURNALD,
        _cleanup_journald,
        schema=SERVICE_SCHEMA_CLEANUP_JOURNALD,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_APT_CACHE,
        _cleanup_apt,
        schema=SERVICE_SCHEMA_CLEANUP_APT,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEANUP_VAR_LOG,
        _cleanup_var_log,
        schema=SERVICE_SCHEMA_CLEANUP_VAR_LOG,
    )


def _unregister_services(hass: HomeAssistant) -> None:
    """Unregister cleanup services."""
    for service in (
        SERVICE_CLEANUP_DOCKER,
        SERVICE_CLEANUP_JOURNALD,
        SERVICE_CLEANUP_APT_CACHE,
        SERVICE_CLEANUP_VAR_LOG,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


def _get_first_coordinator(hass: HomeAssistant) -> RootFSDataUpdateCoordinator | None:
    """Return an arbitrary configured coordinator.

    Services are global for the integration domain, so we currently route them
    to the first configured instance.
    """
    entries: Mapping[str, RootFSDataUpdateCoordinator] = hass.data.get(DOMAIN, {})
    for coordinator in entries.values():
        return coordinator
    return None
