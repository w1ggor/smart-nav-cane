#!/usr/bin/env python3
"""
Awareness mode entry point.

Runs real-time obstacle detection and location recognition, announcing
results through Bluetooth headphones.

Usage:
    python scripts/awareness.py --env lab_test
    python scripts/awareness.py --env lab_test --tof-mock
    python scripts/awareness.py --env lab_test --obstacle-threshold 1.5
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from nav_assistant.audio.guidance import AudioGuidance
from nav_assistant.awareness import AwarenessSystem
from nav_assistant.localization.place_recognizer import PlaceRecognizer
from nav_assistant.mapping.environment import EnvironmentMap
from nav_assistant.obstacle.detector import ObstacleDetector
from nav_assistant.perception.object_detector import ObjectClassifier
from nav_assistant.sensors.tof import ToFSensor
from nav_assistant.sensors.webcam import WebcamSensor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("awareness")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Cane Awareness System")
    parser.add_argument("--env", required=True,
                        help="Environment name to load (must be trained first)")
    parser.add_argument("--tof-mock", action="store_true",
                        help="Use ToF mock mode (no hardware)")
    parser.add_argument("--obstacle-threshold", type=float, default=None,
                        help="Override obstacle alert distance in metres")
    parser.add_argument("--location-cooldown", type=float, default=30.0,
                        help="Seconds before re-announcing the same location (default 30)")
    parser.add_argument("--recognition-interval", type=int, default=3,
                        help="Run location recognition every N cycles (default 3)")
    parser.add_argument("--no-classify", action="store_true",
                        help="Disable YOLO obstacle classification (generic alerts only)")
    args = parser.parse_args()

    cfg = load_config()
    wcam_cfg = cfg["webcam"]
    tof_cfg = cfg["tof"]
    obs_cfg = cfg["obstacle"]
    loc_cfg = cfg["localization"]
    aud_cfg = cfg["audio"]
    perception_cfg = cfg["perception"]

    obstacle_threshold = args.obstacle_threshold or obs_cfg["alert_threshold_m"]

    # --- Build components ---
    audio = AudioGuidance(rate=aud_cfg["rate"], volume=aud_cfg["volume"])
    audio.initialize()

    webcam = WebcamSensor(
        device_name=wcam_cfg.get("device_name"),
        device_index=wcam_cfg["device_index"],
        width=wcam_cfg["width"],
        height=wcam_cfg["height"],
        fps=wcam_cfg["fps"],
    )
    tof = ToFSensor(
        connection=tof_cfg["connection"],
        device_name=tof_cfg.get("device_name", "unicam"),
        device_index=tof_cfg["device_index"],
        mock_mode=args.tof_mock,
    )
    obstacle_detector = ObstacleDetector(
        alert_threshold_m=obstacle_threshold,
        zone_fraction=obs_cfg["detection_zone_fraction"],
    )

    object_classifier = None
    if not args.no_classify:
        object_classifier = ObjectClassifier(
            model_path=perception_cfg["yolo_model_path"],
            confidence_threshold=perception_cfg["confidence_threshold"],
        )
        if object_classifier.is_available:
            logger.info("YOLO object classification enabled")
        else:
            logger.warning("YOLO unavailable — falling back to generic obstacle alerts")

    with EnvironmentMap(args.env, environments_dir=cfg["data"]["environments_dir"]) as env:
        locations = env.list_waypoints()
        if not locations:
            logger.error("Environment '%s' has no trained locations. Run train.py first.", args.env)
            sys.exit(1)

        logger.info("Loaded environment '%s' with %d location(s): %s",
                    args.env, len(locations), [w.label for w in locations])

        recognizer = PlaceRecognizer(
            env,
            confidence_threshold=loc_cfg["confidence_threshold"],
            min_good_matches=loc_cfg["min_good_matches"],
            lowe_ratio=loc_cfg["match_ratio"],
        )
        recognizer.load(kind="location")

        system = AwarenessSystem(
            webcam=webcam,
            tof=tof,
            recognizer=recognizer,
            obstacle_detector=obstacle_detector,
            audio=audio,
            object_classifier=object_classifier,
            recognition_every_n=args.recognition_interval,
            location_cooldown_s=args.location_cooldown,
        )

        # Graceful shutdown on Ctrl+C
        def _on_sigint(sig, frame):
            logger.info("Shutting down...")
            system.stop()

        signal.signal(signal.SIGINT, _on_sigint)

        with webcam, tof:
            system.run()

    audio.shutdown()


if __name__ == "__main__":
    main()
