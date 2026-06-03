"""Shared sensor utilities."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def find_v4l2_device_index(name_pattern: str) -> Optional[int]:
    """
    Parse 'v4l2-ctl --list-devices' and return the first /dev/videoX index
    whose parent device name contains name_pattern (case-insensitive).

    Returns None if v4l2-ctl is unavailable, times out, or no match found.
    Only meaningful on Linux — returns None immediately on other platforms.
    """
    if sys.platform != "linux":
        return None

    try:
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    pattern = name_pattern.lower()
    current_matches = False
    for line in result.stdout.splitlines():
        if not line.startswith("\t"):
            current_matches = pattern in line.lower()
        elif current_matches:
            node = line.strip()
            m = re.match(r"/dev/video(\d+)$", node)
            if m:
                return int(m.group(1))

    return None
