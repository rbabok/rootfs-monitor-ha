"""Cleanup policy behavior tests."""

from custom_components.rootfs_monitor.cleanup import _parse_human_size


def test_parse_human_size_mb() -> None:
    assert _parse_human_size("12.5 MB") == int(12.5 * 1024**2)


def test_parse_human_size_bytes() -> None:
    assert _parse_human_size("128 B") == 128
