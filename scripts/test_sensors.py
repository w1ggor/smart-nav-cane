#!/usr/bin/env python3
"""
Sensor validation script — Phase 1.

Run this on the Raspberry Pi to confirm webcam and ToF camera are working:

    python scripts/test_sensors.py
    python scripts/test_sensors.py --tof-mock   # Skip ToF hardware
    python scripts/test_sensors.py --show       # Display webcam frames (requires display)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
import numpy as np

import yaml

from nav_assistant.sensors.webcam import WebcamSensor
from nav_assistant.sensors.tof import ToFSensor

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_sensors")


def test_webcam(
    device_name: Optional[str] = None,
    device_index: int = 1,
    n_frames: int = 30,
    show: bool = False,
) -> bool:
    label = device_name or f"index={device_index}"
    logger.info("=== Webcam Test (device=%s, frames=%d) ===", label, n_frames)
    try:
        with WebcamSensor(device_name=device_name, device_index=device_index) as cam:
            times = []
            for i in range(n_frames):
                t0 = time.monotonic()
                frame = cam.read_bgr()
                elapsed = (time.monotonic() - t0) * 1000

                times.append(elapsed)
                if i == 0:
                    logger.info("  First frame shape: %s, dtype: %s", frame.shape, frame.dtype)

                if show:
                    cv2.imshow("Webcam Test", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

            if show:
                cv2.destroyAllWindows()

            avg_ms = np.mean(times)
            logger.info("  Captured %d frames | avg capture time: %.1f ms (%.1f FPS)",
                        len(times), avg_ms, 1000 / avg_ms)
        logger.info("  Webcam test: PASSED")
        return True

    except Exception as exc:
        logger.error("  Webcam test FAILED: %s", exc)
        return False


def test_tof(mock: bool = False, n_frames: int = 20) -> bool:
    mode = "MOCK" if mock else "HARDWARE"
    logger.info("=== ToF Camera Test (%s, frames=%d) ===", mode, n_frames)
    try:
        with ToFSensor(mock_mode=mock) as tof:
            for i in range(n_frames):
                t0 = time.monotonic()
                tof_frame = tof.read_tof()
                elapsed = (time.monotonic() - t0) * 1000

                if i == 0:
                    logger.info("  Depth frame shape: %s, dtype: %s",
                                tof_frame.depth.shape, tof_frame.depth.dtype)
                    logger.info("  Depth range: min=%.3fm  max=%.3fm",
                                tof_frame.depth.min(), tof_frame.depth.max())
                    grid = tof_frame.depth_grid()
                    logger.info("  3x3 depth grid (m): %s",
                                " ".join(f"{v:.2f}" for v in grid))
                    fwd = tof_frame.forward_min_depth()
                    logger.info("  Forward min depth: %.3fm", fwd)

                if i % 5 == 0:
                    logger.info("  Frame %2d | read time: %.1f ms", i, elapsed)

        logger.info("  ToF test: PASSED")
        return True

    except Exception as exc:
        logger.error("  ToF test FAILED: %s", exc)
        return False


def main() -> None:
    cfg = _load_config()
    wcam_cfg = cfg.get("webcam", {})
    default_device_name = wcam_cfg.get("device_name", "C270 HD WEBCAM")
    default_device_index = wcam_cfg.get("device_index", 1)

    parser = argparse.ArgumentParser(description="Validate webcam and ToF sensors")
    parser.add_argument("--webcam-name", type=str, default=default_device_name,
                        help="V4L2 device name substring for auto-detection")
    parser.add_argument("--webcam-index", type=int, default=default_device_index,
                        help="Fallback device index if auto-detection fails")
    parser.add_argument("--tof-mock", action="store_true", help="Run ToF in mock mode")
    parser.add_argument("--show", action="store_true", help="Show webcam frames in a window")
    parser.add_argument("--skip-webcam", action="store_true")
    parser.add_argument("--skip-tof", action="store_true")
    args = parser.parse_args()

    results: dict[str, bool] = {}

    if not args.skip_webcam:
        results["webcam"] = test_webcam(
            device_name=args.webcam_name,
            device_index=args.webcam_index,
            show=args.show,
        )

    if not args.skip_tof:
        results["tof"] = test_tof(mock=args.tof_mock)

    print("\n=== Summary ===")
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name:10s}: {status}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
