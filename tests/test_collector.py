"""Collector parser tests."""

from custom_components.rootfs_monitor.collector import _parse_journal_disk_usage


def test_parse_journal_disk_usage_gib() -> None:
    value = _parse_journal_disk_usage("Archived and active journals take up 1.5G in the file system.")
    assert value == int(1.5 * 1024**3)


def test_parse_journal_disk_usage_mb() -> None:
    value = _parse_journal_disk_usage("Archived and active journals take up 256.0M in the file system.")
    assert value == int(256.0 * 1024**2)
