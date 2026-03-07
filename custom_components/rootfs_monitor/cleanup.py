"""Cleanup actions for major rootfs consumers with safety defaults."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import glob
import os
import shlex
import shutil
import subprocess
from typing import Any, Mapping

from homeassistant.core import HomeAssistant

from .const import (
    ATTR_ALL_IMAGES,
    ATTR_DRY_RUN,
    ATTR_INCLUDE_VOLUMES,
    ATTR_MIN_AGE_DAYS,
    ATTR_MODE,
    ATTR_UNTIL,
    ATTR_VACUUM_SIZE,
    ATTR_VACUUM_TIME,
    MODE_AUTOCLEAN,
)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _: None):
        for name in files:
            full = Path(root) / name
            try:
                total += full.stat().st_size
            except OSError:
                continue
    return total


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except (OSError, subprocess.TimeoutExpired) as err:
        return 1, "", str(err)


async def run_docker_cleanup(
    hass: HomeAssistant,
    host_root: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Run docker prune with conservative defaults and optional filters."""
    return await hass.async_add_executor_job(_run_docker_cleanup_sync, payload)


def _run_docker_cleanup_sync(payload: Mapping[str, Any]) -> dict[str, Any]:
    docker = shutil.which("docker")
    if not docker:
        return {
            "status": "error",
            "target": "docker",
            "message": "docker CLI not available in container",
            "dry_run": True,
            "reclaimed_bytes": 0,
        }

    dry_run = bool(payload.get(ATTR_DRY_RUN, True))
    all_images = bool(payload.get(ATTR_ALL_IMAGES, False))
    include_volumes = bool(payload.get(ATTR_INCLUDE_VOLUMES, False))
    until = payload.get(ATTR_UNTIL)

    preview_cmd = [docker, "system", "df"]
    rc_before, out_before, err_before = _run(preview_cmd, timeout=30)
    if rc_before != 0:
        return {
            "status": "error",
            "target": "docker",
            "message": err_before.strip()[:300],
            "dry_run": dry_run,
            "reclaimed_bytes": 0,
        }

    prune_cmd = [docker, "system", "prune", "-f"]
    if all_images:
        prune_cmd.append("-a")
    if include_volumes:
        prune_cmd.append("--volumes")
    if isinstance(until, str) and until.strip():
        prune_cmd.extend(["--filter", f"until={until.strip()}"])

    if dry_run:
        return {
            "status": "preview",
            "target": "docker",
            "message": f"Would run: {' '.join(shlex.quote(p) for p in prune_cmd)}",
            "dry_run": True,
            "reclaimed_bytes": 0,
            "details": out_before.strip()[:1000],
        }

    rc, out, err = _run(prune_cmd, timeout=240)
    if rc != 0:
        return {
            "status": "error",
            "target": "docker",
            "message": err.strip()[:300],
            "dry_run": False,
            "reclaimed_bytes": 0,
        }

    return {
        "status": "success",
        "target": "docker",
        "message": "Docker prune completed",
        "dry_run": False,
        "reclaimed_bytes": _extract_reclaimed_space(out),
        "details": out.strip()[:1000],
    }


async def run_journald_cleanup(
    hass: HomeAssistant,
    host_root: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Vacuum archived journald files in the mounted host journal directory."""
    return await hass.async_add_executor_job(_run_journald_cleanup_sync, host_root, payload)


def _run_journald_cleanup_sync(host_root: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    journalctl = shutil.which("journalctl")
    if not journalctl:
        return {
            "status": "error",
            "target": "journald",
            "message": "journalctl binary missing",
            "dry_run": True,
            "reclaimed_bytes": 0,
        }

    journal_dir = Path(host_root) / "var" / "log" / "journal"
    if not journal_dir.exists():
        return {
            "status": "error",
            "target": "journald",
            "message": f"Journal directory not found: {journal_dir}",
            "dry_run": True,
            "reclaimed_bytes": 0,
        }

    dry_run = bool(payload.get(ATTR_DRY_RUN, True))
    vacuum_size = payload.get(ATTR_VACUUM_SIZE)
    vacuum_time = payload.get(ATTR_VACUUM_TIME)

    if not vacuum_size and not vacuum_time:
        vacuum_size = "1G"

    cmd = [journalctl, f"--directory={journal_dir}", "--rotate"]
    if vacuum_size:
        cmd.append(f"--vacuum-size={vacuum_size}")
    if vacuum_time:
        cmd.append(f"--vacuum-time={vacuum_time}")

    before = _dir_size(journal_dir)

    if dry_run:
        return {
            "status": "preview",
            "target": "journald",
            "message": f"Would run: {' '.join(shlex.quote(p) for p in cmd)}",
            "dry_run": True,
            "reclaimed_bytes": 0,
            "reclaimable_bytes_estimate": before,
        }

    rc, out, err = _run(cmd, timeout=180)
    if rc != 0:
        return {
            "status": "error",
            "target": "journald",
            "message": err.strip()[:300],
            "dry_run": False,
            "reclaimed_bytes": 0,
        }

    after = _dir_size(journal_dir)
    reclaimed = max(before - after, 0)
    return {
        "status": "success",
        "target": "journald",
        "message": "Journald vacuum completed",
        "dry_run": False,
        "reclaimed_bytes": reclaimed,
        "details": out.strip()[:1000],
    }


async def run_apt_cache_cleanup(
    hass: HomeAssistant,
    host_root: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Run apt cache cleanup through host chroot when available."""
    return await hass.async_add_executor_job(_run_apt_cache_cleanup_sync, host_root, payload)


def _run_apt_cache_cleanup_sync(host_root: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    dry_run = bool(payload.get(ATTR_DRY_RUN, True))
    mode = str(payload.get(ATTR_MODE, MODE_AUTOCLEAN))

    cache_dir = Path(host_root) / "var" / "cache" / "apt" / "archives"
    before = _dir_size(cache_dir)

    chroot = shutil.which("chroot")
    host_apt = Path(host_root) / "usr" / "bin" / "apt-get"

    if not chroot or not host_apt.exists():
        return {
            "status": "error",
            "target": "apt_cache",
            "message": "Host apt-get not reachable via chroot",
            "dry_run": dry_run,
            "reclaimed_bytes": 0,
        }

    apt_action = "autoclean" if mode == MODE_AUTOCLEAN else "clean"

    cmd = [chroot, host_root, "apt-get"]
    if dry_run:
        cmd.append("-s")
    cmd.extend(["-y", apt_action])

    rc, out, err = _run(cmd, timeout=300)
    if rc != 0:
        return {
            "status": "error",
            "target": "apt_cache",
            "message": err.strip()[:300],
            "dry_run": dry_run,
            "reclaimed_bytes": 0,
        }

    if dry_run:
        return {
            "status": "preview",
            "target": "apt_cache",
            "message": f"Would run: {' '.join(shlex.quote(p) for p in cmd)}",
            "dry_run": True,
            "reclaimed_bytes": 0,
            "reclaimable_bytes_estimate": before,
            "details": out.strip()[:1000],
        }

    after = _dir_size(cache_dir)
    reclaimed = max(before - after, 0)
    return {
        "status": "success",
        "target": "apt_cache",
        "message": f"apt-get {apt_action} completed",
        "dry_run": False,
        "reclaimed_bytes": reclaimed,
        "details": out.strip()[:1000],
    }


async def run_var_log_cleanup(
    hass: HomeAssistant,
    host_root: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Clean old rotated log files in /var/log with retention guard."""
    return await hass.async_add_executor_job(_run_var_log_cleanup_sync, host_root, payload)


def _run_var_log_cleanup_sync(host_root: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    dry_run = bool(payload.get(ATTR_DRY_RUN, True))
    min_age_days = int(payload.get(ATTR_MIN_AGE_DAYS, 7))

    var_log = Path(host_root) / "var" / "log"
    if not var_log.exists():
        return {
            "status": "error",
            "target": "var_log",
            "message": f"Missing log directory: {var_log}",
            "dry_run": dry_run,
            "reclaimed_bytes": 0,
        }

    now = datetime.now(timezone.utc)
    min_age = timedelta(days=min_age_days)

    patterns = [
        "**/*.gz",
        "**/*.old",
        "**/*.1",
        "**/*.2",
        "**/*.3",
        "**/*.4",
        "**/*.5",
        "**/*.6",
        "**/*.7",
        "**/*.8",
        "**/*.9",
    ]

    candidates: list[Path] = []
    for pattern in patterns:
        for path_text in glob.glob(str(var_log / pattern), recursive=True):
            path = Path(path_text)
            if not path.is_file() or path.is_symlink():
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if now - mtime >= min_age:
                candidates.append(path)

    candidates = sorted(set(candidates))
    reclaimable = 0
    for path in candidates:
        try:
            reclaimable += path.stat().st_size
        except OSError:
            continue

    if dry_run:
        return {
            "status": "preview",
            "target": "var_log",
            "message": f"Would delete {len(candidates)} rotated log files older than {min_age_days}d",
            "dry_run": True,
            "reclaimed_bytes": 0,
            "reclaimable_bytes_estimate": reclaimable,
        }

    deleted = 0
    reclaimed = 0
    for path in candidates:
        try:
            size = path.stat().st_size
            path.unlink()
            deleted += 1
            reclaimed += size
        except OSError:
            continue

    return {
        "status": "success",
        "target": "var_log",
        "message": f"Deleted {deleted} rotated log files",
        "dry_run": False,
        "reclaimed_bytes": reclaimed,
    }


def _extract_reclaimed_space(output: str) -> int:
    """Parse docker prune output for reclaimed bytes if reported."""
    for line in output.splitlines():
        if "Total reclaimed space:" not in line:
            continue
        size_text = line.split("Total reclaimed space:", 1)[1].strip()
        return _parse_human_size(size_text)
    return 0


def _parse_human_size(value: str) -> int:
    tokens = value.split()
    if not tokens:
        return 0
    number = tokens[0]
    unit = tokens[1] if len(tokens) > 1 else "B"
    unit = unit.upper().replace("IB", "B")
    factor = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "PB": 1024**5,
    }.get(unit, 1)

    try:
        return int(float(number) * factor)
    except ValueError:
        return 0
