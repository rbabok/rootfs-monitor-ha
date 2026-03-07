"""Data update coordinator for RootFS monitor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .collector import collect_usage_snapshot
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
)


class RootFSDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that refreshes rootfs usage snapshots."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        config = {**entry.data, **entry.options}

        self.host_root: str = config.get(CONF_HOST_ROOT, DEFAULT_HOST_ROOT)
        self.top_n: int = int(config.get(CONF_TOP_N, DEFAULT_TOP_N))
        self.warn_percent: int = int(config.get(CONF_WARN_PERCENT, DEFAULT_WARN_PERCENT))
        self.crit_percent: int = int(config.get(CONF_CRIT_PERCENT, DEFAULT_CRIT_PERCENT))

        interval_seconds = int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS))

        self.last_cleanup: dict[str, Any] = {
            "status": "never",
            "target": "none",
            "dry_run": True,
            "reclaimed_bytes": 0,
            "message": "No cleanup executed yet",
            "at": None,
        }

        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_seconds),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch usage data from the mounted host rootfs."""
        try:
            snapshot = await self.hass.async_add_executor_job(
                collect_usage_snapshot,
                self.host_root,
                self.top_n,
            )
        except Exception as err:
            raise UpdateFailed(f"Failed collecting rootfs snapshot: {err}") from err

        root_used = snapshot["rootfs"].get("used_percent", 0)
        pressure = "normal"
        if root_used >= self.crit_percent:
            pressure = "critical"
        elif root_used >= self.warn_percent:
            pressure = "warning"

        snapshot["pressure"] = {
            "level": pressure,
            "warn_percent": self.warn_percent,
            "crit_percent": self.crit_percent,
        }
        snapshot["last_cleanup"] = self.last_cleanup

        return snapshot

    def set_last_cleanup(self, result: dict[str, Any]) -> None:
        """Store latest cleanup result for diagnostic sensors."""
        payload = dict(result)
        payload.setdefault("status", "unknown")
        payload.setdefault("target", "unknown")
        payload.setdefault("dry_run", True)
        payload.setdefault("reclaimed_bytes", 0)
        payload.setdefault("message", "")
        payload["at"] = datetime.now(timezone.utc).isoformat()
        self.last_cleanup = payload
