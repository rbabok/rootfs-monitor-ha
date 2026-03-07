"""Constants for the RootFS monitor integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "rootfs_monitor"
PLATFORMS = ["sensor"]

CONF_HOST_ROOT = "host_root"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TOP_N = "top_n"
CONF_WARN_PERCENT = "warn_percent"
CONF_CRIT_PERCENT = "crit_percent"

DEFAULT_HOST_ROOT = "/host"
DEFAULT_SCAN_INTERVAL_SECONDS = 300
DEFAULT_TOP_N = 5
DEFAULT_WARN_PERCENT = 80
DEFAULT_CRIT_PERCENT = 90

MIN_SCAN_INTERVAL_SECONDS = 60
MAX_SCAN_INTERVAL_SECONDS = 3600
MAX_TOP_N = 10

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)

SERVICE_CLEANUP_DOCKER = "cleanup_docker"
SERVICE_CLEANUP_JOURNALD = "cleanup_journald"
SERVICE_CLEANUP_APT_CACHE = "cleanup_apt_cache"
SERVICE_CLEANUP_VAR_LOG = "cleanup_var_log"

ATTR_DRY_RUN = "dry_run"
ATTR_ALL_IMAGES = "all_images"
ATTR_INCLUDE_VOLUMES = "include_volumes"
ATTR_UNTIL = "until"
ATTR_VACUUM_SIZE = "vacuum_size"
ATTR_VACUUM_TIME = "vacuum_time"
ATTR_MODE = "mode"
ATTR_MIN_AGE_DAYS = "min_age_days"

MODE_AUTOCLEAN = "autoclean"
MODE_CLEAN = "clean"
