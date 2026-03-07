# RootFS Monitor Home Assistant Integration

Custom Home Assistant integration to investigate rootfs usage, expose exact per-consumer sensors, and run guarded cleanup for high-impact consumers.

## Features

- Rootfs exact sensors: total, used, free, used percent.
- Investigation-first top consumer ranking (Top N paths by bytes).
- Critical consumer sensors:
  - Docker total/images/containers/volumes/build cache bytes.
  - Journald disk usage bytes.
  - APT cache bytes.
  - `/var/log` bytes.
- Cleanup services with dry-run defaults:
  - `rootfs_monitor.cleanup_docker`
  - `rootfs_monitor.cleanup_journald`
  - `rootfs_monitor.cleanup_apt_cache`
  - `rootfs_monitor.cleanup_var_log`
- Cleanup diagnostics:
  - Last cleanup status and reclaimed bytes.

## Required Container Access

This integration is designed for Home Assistant running in Docker.

Recommended mounts:

- Host root: `/:/host`
- Docker socket: `/var/run/docker.sock:/var/run/docker.sock`

Important:

- Monitoring works with read-only host mount.
- Cleanup requires write access on target paths.
- If your host root is mounted read-only, cleanup services will fail safely.

## Install

1. Copy `custom_components/rootfs_monitor` into your Home Assistant config directory.
2. Restart Home Assistant.
3. Add integration from UI: **Settings -> Devices & Services -> Add Integration -> RootFS Monitor**.
4. Configure host mount path (default `/host`) and thresholds.

## Service Safety Model

All cleanup services default to `dry_run: true`.

- Docker cleanup:
  - Default command: `docker system prune -f`
  - Optional `all_images: true` adds `-a`
  - Optional `include_volumes: true` adds `--volumes`
  - Optional `until: "168h"` filter supported
- Journald cleanup:
  - Uses `journalctl --directory=/host/var/log/journal --rotate --vacuum-*`
  - If no vacuum settings provided, defaults to `--vacuum-size=1G`
- APT cache cleanup:
  - Uses `chroot /host apt-get -y autoclean|clean`
  - Requires host apt binary and `chroot` in HA container
- `/var/log` cleanup:
  - Deletes only rotated/compressed files older than `min_age_days`
  - Never deletes active plain log files directly

## Suggested Automations

1. Notify on pressure `warning`.
2. Run dry-run cleanup service and include estimate in notification.
3. Require manual confirmation before `dry_run: false` actions.

## Notes

- Docker/journal/apt binaries must be available in the Home Assistant container environment.
- If binaries are unavailable, related sensors become unavailable or keep 0 with reason attributes.
- This repository includes starter tests for parser and cleanup guardrails.
