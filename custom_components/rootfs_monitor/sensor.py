"""Sensor platform for RootFS Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RootFSDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class RootFSSensorDescription(SensorEntityDescription):
    """Describe RootFS Monitor sensor entities."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


BASE_SENSORS: tuple[RootFSSensorDescription, ...] = (
    RootFSSensorDescription(
        key="rootfs_total_bytes",
        translation_key="rootfs_total_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["rootfs"].get("total_bytes"),
    ),
    RootFSSensorDescription(
        key="rootfs_used_bytes",
        translation_key="rootfs_used_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["rootfs"].get("used_bytes"),
    ),
    RootFSSensorDescription(
        key="rootfs_free_bytes",
        translation_key="rootfs_free_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["rootfs"].get("free_bytes"),
    ),
    RootFSSensorDescription(
        key="rootfs_used_percent",
        translation_key="rootfs_used_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data["rootfs"].get("used_percent"),
    ),
    RootFSSensorDescription(
        key="rootfs_pressure_level",
        translation_key="rootfs_pressure_level",
        device_class=SensorDeviceClass.ENUM,
        options=["normal", "warning", "critical"],
        value_fn=lambda data: data["pressure"].get("level"),
        attrs_fn=lambda data: {
            "warn_percent": data["pressure"].get("warn_percent"),
            "crit_percent": data["pressure"].get("crit_percent"),
        },
    ),
    RootFSSensorDescription(
        key="docker_total_bytes",
        translation_key="docker_total_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["docker"].get("total_bytes"),
        attrs_fn=lambda data: {
            "docker_available": data["consumers"]["docker"].get("available", False),
            "docker_source": data["consumers"]["docker"].get("source"),
            "docker_reason": data["consumers"]["docker"].get("reason"),
        },
    ),
    RootFSSensorDescription(
        key="docker_images_bytes",
        translation_key="docker_images_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["docker"].get("images_bytes"),
    ),
    RootFSSensorDescription(
        key="docker_containers_bytes",
        translation_key="docker_containers_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["docker"].get("containers_bytes"),
    ),
    RootFSSensorDescription(
        key="docker_volumes_bytes",
        translation_key="docker_volumes_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["docker"].get("volumes_bytes"),
    ),
    RootFSSensorDescription(
        key="docker_build_cache_bytes",
        translation_key="docker_build_cache_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["docker"].get("build_cache_bytes"),
    ),
    RootFSSensorDescription(
        key="journald_disk_usage_bytes",
        translation_key="journald_disk_usage_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["journald"].get("bytes"),
    ),
    RootFSSensorDescription(
        key="apt_cache_bytes",
        translation_key="apt_cache_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["apt_cache"].get("bytes"),
    ),
    RootFSSensorDescription(
        key="var_log_bytes",
        translation_key="var_log_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["consumers"]["var_log"].get("bytes"),
    ),
    RootFSSensorDescription(
        key="last_cleanup_status",
        translation_key="last_cleanup_status",
        device_class=SensorDeviceClass.ENUM,
        options=["never", "preview", "success", "error", "unknown"],
        value_fn=lambda data: data["last_cleanup"].get("status", "unknown"),
        attrs_fn=lambda data: {
            "target": data["last_cleanup"].get("target"),
            "dry_run": data["last_cleanup"].get("dry_run"),
            "message": data["last_cleanup"].get("message"),
            "at": data["last_cleanup"].get("at"),
        },
    ),
    RootFSSensorDescription(
        key="last_cleanup_reclaimed_bytes",
        translation_key="last_cleanup_reclaimed_bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["last_cleanup"].get("reclaimed_bytes", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RootFS sensors for a config entry."""
    coordinator: RootFSDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        RootFSValueSensor(coordinator, entry, description)
        for description in BASE_SENSORS
    ]

    for idx in range(1, coordinator.top_n + 1):
        entities.append(RootFSTopConsumerSensor(coordinator, entry, idx))

    async_add_entities(entities)


class RootFSValueSensor(CoordinatorEntity[RootFSDataUpdateCoordinator], SensorEntity):
    """Generic value sensor backed by coordinator data."""

    entity_description: RootFSSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RootFSDataUpdateCoordinator,
        entry: ConfigEntry,
        description: RootFSSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="RootFS Monitor",
            manufacturer="Custom",
            model="Host RootFS",
            configuration_url="https://www.home-assistant.io/",
        )

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data or not self.entity_description.attrs_fn:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class RootFSTopConsumerSensor(CoordinatorEntity[RootFSDataUpdateCoordinator], SensorEntity):
    """Entity exposing ranked top consumer usage."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: RootFSDataUpdateCoordinator,
        entry: ConfigEntry,
        rank: int,
    ) -> None:
        super().__init__(coordinator)
        self._rank = rank
        self._attr_translation_key = "top_rootfs_consumer"
        self._attr_name = f"Top RootFS Consumer {rank}"
        self._attr_unique_id = f"{entry.entry_id}_top_rootfs_consumer_{rank}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="RootFS Monitor",
            manufacturer="Custom",
            model="Host RootFS",
        )

    @property
    def native_value(self) -> int | None:
        item = self._current_item
        if not item:
            return None
        return int(item.get("bytes", 0))

    @property
    def available(self) -> bool:
        return self._current_item is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        item = self._current_item
        if not item:
            return None
        return {
            "path": item.get("path"),
            "percent_rootfs": item.get("percent_rootfs"),
            "rank": self._rank,
        }

    @property
    def _current_item(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        if not data:
            return None
        top = data.get("top_consumers", [])
        idx = self._rank - 1
        if idx < 0 or idx >= len(top):
            return None
        return top[idx]
