# Installation

## Option 1: HACS Custom Repository (Recommended)

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Select the three-dot menu and choose `Custom repositories`.
4. Add this repository URL: `https://github.com/rbabok/rootfs-monitor-ha`.
5. Category: `Integration`.
6. Install `RootFS Monitor` from HACS.
7. Restart Home Assistant.
8. Add integration from `Settings -> Devices & Services -> Add Integration`.

## Option 2: Manual URL Download

1. Download the latest release zip from GitHub Releases.
2. Extract `custom_components/rootfs_monitor` into your Home Assistant config directory.
3. Restart Home Assistant.
4. Add integration from UI.

## Required Runtime Access

For Home Assistant running in Docker:

- Mount host root to container, usually `/:/host`.
- Mount Docker socket for Docker metrics and cleanup: `/var/run/docker.sock:/var/run/docker.sock`.

Cleanup services need write permissions on target host paths.
