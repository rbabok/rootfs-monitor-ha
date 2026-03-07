"""Data collection helpers for RootFS monitor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import os
import re
import shutil
import subprocess
from typing import Any

DOCKER_SIZE_KEYS = {
    "images",
    "imagessize",
    "imagespace",
    "containers",
    "containerssize",
    "containerspace",
    "volumes",
    "localvolumes",
    "localvolumessize",
    "buildcache",
    "buildcachesize",
}

SIZE_RE = re.compile(r"([0-9]*\.?[0-9]+)\s*([KMGTPE]?i?B|B)", re.IGNORECASE)


@dataclass(slots=True)
class CommandResult:
    """Result of running a command."""

    return_code: int
    stdout: str
    stderr: str


def collect_usage_snapshot(host_root: str, top_n: int) -> dict[str, Any]:
    """Collect a full snapshot with rootfs and critical consumer usage."""
    root_path = Path(host_root)
    rootfs = _collect_rootfs_totals(root_path)

    top_consumers = _collect_top_level_consumers(root_path, rootfs["total_bytes"], top_n)

    docker_data = _collect_docker_usage()
    journald_bytes = _collect_journald_bytes(root_path)
    apt_bytes = _safe_dir_size(root_path / "var" / "cache" / "apt" / "archives")
    var_log_bytes = _safe_dir_size(root_path / "var" / "log")

    return {
        "rootfs": rootfs,
        "consumers": {
            "docker": docker_data,
            "journald": {"bytes": journald_bytes},
            "apt_cache": {"bytes": apt_bytes},
            "var_log": {"bytes": var_log_bytes},
        },
        "top_consumers": top_consumers,
    }


def _collect_rootfs_totals(root_path: Path) -> dict[str, Any]:
    """Collect root filesystem totals for the mounted host root."""
    stats = os.statvfs(root_path)
    total_bytes = stats.f_blocks * stats.f_frsize
    free_bytes = stats.f_bavail * stats.f_frsize
    used_bytes = max(total_bytes - free_bytes, 0)
    used_percent = (used_bytes / total_bytes * 100) if total_bytes else 0.0

    return {
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "free_bytes": free_bytes,
        "used_percent": round(used_percent, 2),
    }


def _collect_top_level_consumers(
    root_path: Path,
    total_bytes: int,
    top_n: int,
) -> list[dict[str, Any]]:
    """Collect top-level directory consumers under rootfs."""
    du = shutil.which("du")
    if du:
        result = _run_command([du, "-x", "-d", "1", "-B1", str(root_path)], timeout=40)
        if result.return_code == 0 and result.stdout.strip():
            return _parse_du_top_level(result.stdout, root_path, total_bytes, top_n)

    # Fallback for environments without du.
    totals: list[tuple[str, int]] = []
    for child in root_path.iterdir():
        try:
            bytes_used = _safe_dir_size(child)
        except OSError:
            continue
        display = _display_path(child, root_path)
        totals.append((display, bytes_used))

    totals.sort(key=lambda item: item[1], reverse=True)
    out: list[dict[str, Any]] = []
    for display, bytes_used in totals[:top_n]:
        percent_root = (bytes_used / total_bytes * 100) if total_bytes else 0
        out.append(
            {
                "path": display,
                "bytes": int(bytes_used),
                "percent_rootfs": round(percent_root, 2),
            }
        )
    return out


def _parse_du_top_level(
    output: str,
    root_path: Path,
    total_bytes: int,
    top_n: int,
) -> list[dict[str, Any]]:
    """Parse GNU du depth output into top consumer objects."""
    entries: list[tuple[str, int]] = []
    root_text = str(root_path)

    for line in output.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        size_str, path_str = parts
        if path_str == root_text:
            continue
        try:
            size = int(size_str)
        except ValueError:
            continue
        display = _display_path(Path(path_str), root_path)
        entries.append((display, size))

    entries.sort(key=lambda item: item[1], reverse=True)

    out: list[dict[str, Any]] = []
    for display, size in entries[:top_n]:
        percent_root = (size / total_bytes * 100) if total_bytes else 0
        out.append(
            {
                "path": display,
                "bytes": int(size),
                "percent_rootfs": round(percent_root, 2),
            }
        )
    return out


def _collect_docker_usage() -> dict[str, Any]:
    """Collect Docker disk usage summary when docker CLI is available."""
    docker = shutil.which("docker")
    if not docker:
        return {"available": False, "reason": "docker_cli_missing"}

    result = _run_command([docker, "system", "df", "--format", "json"], timeout=20)
    if result.return_code == 0 and result.stdout.strip():
        parsed = _parse_docker_json(result.stdout)
        if parsed:
            parsed["available"] = True
            parsed["source"] = "json"
            return parsed

    # Fallback to table parsing.
    result = _run_command([docker, "system", "df"], timeout=20)
    if result.return_code == 0 and result.stdout.strip():
        parsed = _parse_docker_table(result.stdout)
        if parsed:
            parsed["available"] = True
            parsed["source"] = "table"
            return parsed

    return {
        "available": False,
        "reason": "docker_df_failed",
        "stderr": result.stderr.strip()[:300],
    }


def _parse_docker_json(text: str) -> dict[str, Any] | None:
    """Parse docker system df JSON output into bytes by category."""
    text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    # Newer CLIs may return a dict with grouped fields.
    if isinstance(payload, dict):
        images = _extract_size(payload, "images")
        containers = _extract_size(payload, "containers")
        volumes = _extract_size(payload, "volumes") or _extract_size(payload, "localvolumes")
        build_cache = _extract_size(payload, "buildcache")

        total = sum(v for v in [images, containers, volumes, build_cache] if v is not None)
        if total > 0 or any(v is not None for v in [images, containers, volumes, build_cache]):
            return {
                "images_bytes": images or 0,
                "containers_bytes": containers or 0,
                "volumes_bytes": volumes or 0,
                "build_cache_bytes": build_cache or 0,
                "total_bytes": total,
            }

    # Some CLIs may emit JSON lines; parse as type rows.
    if isinstance(payload, list):
        return _parse_docker_json_rows(payload)

    return None


def _parse_docker_json_rows(rows: list[Any]) -> dict[str, Any] | None:
    """Parse docker JSON rows fallback shape."""
    images = containers = volumes = build_cache = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        row_type = str(row.get("Type", "")).lower()
        row_size = _coerce_size_to_bytes(row.get("Size", 0))
        if row_type.startswith("image"):
            images += row_size
        elif row_type.startswith("container"):
            containers += row_size
        elif "volume" in row_type:
            volumes += row_size
        elif "build" in row_type:
            build_cache += row_size

    total = images + containers + volumes + build_cache
    if total == 0:
        return None

    return {
        "images_bytes": images,
        "containers_bytes": containers,
        "volumes_bytes": volumes,
        "build_cache_bytes": build_cache,
        "total_bytes": total,
    }


def _parse_docker_table(text: str) -> dict[str, Any] | None:
    """Parse docker system df table output."""
    images = containers = volumes = build_cache = 0
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    for line in lines[1:]:
        # Expected shape: TYPE TOTAL ACTIVE SIZE RECLAIMABLE
        parts = re.split(r"\s{2,}", line)
        if len(parts) < 4:
            continue
        row_type = parts[0].lower()
        size = _coerce_size_to_bytes(parts[3])
        if row_type.startswith("images"):
            images = size
        elif row_type.startswith("containers"):
            containers = size
        elif "volume" in row_type:
            volumes = size
        elif "build" in row_type:
            build_cache = size

    total = images + containers + volumes + build_cache
    return {
        "images_bytes": images,
        "containers_bytes": containers,
        "volumes_bytes": volumes,
        "build_cache_bytes": build_cache,
        "total_bytes": total,
    }


def _collect_journald_bytes(root_path: Path) -> int:
    """Collect journald bytes using journalctl, with fallback to dir size."""
    journalctl = shutil.which("journalctl")
    journal_dir = root_path / "var" / "log" / "journal"

    if journalctl and journal_dir.exists():
        result = _run_command(
            [journalctl, f"--directory={journal_dir}", "--disk-usage"],
            timeout=20,
        )
        if result.return_code == 0:
            size = _parse_journal_disk_usage(result.stdout)
            if size is not None:
                return size

    return _safe_dir_size(journal_dir)


def _parse_journal_disk_usage(text: str) -> int | None:
    """Parse `journalctl --disk-usage` output."""
    match = SIZE_RE.search(text)
    if not match:
        return None
    value, unit = match.groups()
    return _to_bytes(value, unit)


def _safe_dir_size(path: Path) -> int:
    """Return directory byte size, handling missing or inaccessible paths."""
    if not path.exists():
        return 0

    du = shutil.which("du")
    if du:
        result = _run_command([du, "-sb", str(path)], timeout=40)
        if result.return_code == 0 and result.stdout.strip():
            first = result.stdout.split("\t", 1)[0].split(" ", 1)[0]
            try:
                return int(first)
            except ValueError:
                pass

    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _: None):
        for name in files:
            file_path = Path(root) / name
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _display_path(path: Path, root_path: Path) -> str:
    """Convert host-root path to real rootfs-like path."""
    try:
        relative = path.relative_to(root_path)
    except ValueError:
        return str(path)
    text = "/" + str(relative).strip("/")
    return text if text != "/" else "/"


def _run_command(cmd: list[str], timeout: int = 20) -> CommandResult:
    """Run a command and capture output without shell expansion."""
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return CommandResult(return_code=1, stdout="", stderr=str(err))


def _extract_size(payload: dict[str, Any], field: str) -> int | None:
    """Extract a byte value from common docker JSON field names."""
    field_lower = field.lower()

    for key, value in payload.items():
        key_lower = str(key).lower()
        if field_lower in key_lower and any(token in key_lower for token in ["size", "space", field_lower]):
            size = _coerce_size_to_bytes(value)
            if size is not None:
                return size

    nested = payload.get(field)
    if isinstance(nested, dict):
        for nested_key, nested_value in nested.items():
            if "size" in str(nested_key).lower() or str(nested_key).lower() in DOCKER_SIZE_KEYS:
                size = _coerce_size_to_bytes(nested_value)
                if size is not None:
                    return size

    return None


def _coerce_size_to_bytes(value: Any) -> int:
    """Convert docker size values into integer bytes."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str):
        # Drop reclaimable percentages and keep only the first size token.
        match = SIZE_RE.search(value)
        if not match:
            try:
                return int(value)
            except ValueError:
                return 0
        number, unit = match.groups()
        return _to_bytes(number, unit)
    return 0


def _to_bytes(number_text: str, unit_text: str) -> int:
    """Translate number/unit text into bytes using binary units."""
    number = float(number_text)
    unit = unit_text.upper().replace("IB", "B")

    factor_map = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "PB": 1024**5,
        "EB": 1024**6,
    }
    factor = factor_map.get(unit, 1)
    return max(int(math.floor(number * factor)), 0)
