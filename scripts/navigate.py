#!/usr/bin/env python3
"""
Navigation mode — Phase 3/4.

Localizes the user in a learned environment and guides them to a destination
via audio instructions. Runs a continuous loop:

  1. Capture webcam frame → localize → current waypoint
  2. Capture ToF frame   → check for obstacles → alert if needed
  3. If localized: advance navigator → speak next instruction

Usage:
    python scripts/navigate.py --env my_home --destination kitchen_door
    python scripts/navigate.py --env my_home --destination kitchen_door --tof-mock
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from nav_assistant.audio.guidance import AudioGuidance
from nav_assistant.localization.place_recognizer import PlaceRecognizer
from nav_assistant.mapping.environment import EnvironmentMap
from nav_assistant.navigation.navigator import Navigator, NavigationState
from nav_assistant.navigation.route_graph import RouteGraph
from nav_assistant.obstacle.detector import ObstacleDetector
from nav_assistant.sensors.tof import ToFSensor
from nav_assistant.sensors.webcam import WebcamSensor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("navigate")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"
_RUNNING = True


def _handle_sigint(sig, frame):
    global _RUNNING
    _RUNNING = False
    print("\nNavigation stopped.")


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Navigation mode")
    parser.add_argument("--env", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--tof-mock", action="store_true")
    parser.add_argument("--webcam-index", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config()
    signal.signal(signal.SIGINT, _handle_sigint)

    audio = AudioGuidance(
        rate=cfg["audio"]["rate"],
        volume=cfg["audio"]["volume"],
    )
    audio.initialize()

    webcam = WebcamSensor(
        device_name=cfg["webcam"].get("device_name"),
        device_index=cfg["webcam"]["device_index"],
        width=cfg["webcam"]["width"],
        height=cfg["webcam"]["height"],
    )
    tof = ToFSensor(
        connection=cfg["tof"]["connection"],
        device_name=cfg["tof"].get("device_name", "unicam"),
        device_index=cfg["tof"]["device_index"],
        mock_mode=args.tof_mock,
    )
    obstacle_detector = ObstacleDetector(
        alert_threshold_m=cfg["obstacle"]["alert_threshold_m"],
        zone_fraction=cfg["obstacle"]["detection_zone_fraction"],
    )

    with EnvironmentMap(args.env, environments_dir=cfg["data"]["environments_dir"]) as env:
        recognizer = PlaceRecognizer(
            env,
            confidence_threshold=cfg["localization"]["confidence_threshold"],
            min_good_matches=cfg["localization"]["min_good_matches"],
            lowe_ratio=cfg["localization"]["match_ratio"],
        )
        recognizer.load()

        graph = RouteGraph(env)
        graph.build()

        navigator = Navigator(graph)

        audio.speak("Navigation system ready. Localizing...")

        last_waypoint_id = None
        navigation_started = False

        with webcam, tof:
            while _RUNNING:
                loop_start = time.monotonic()

                # --- Obstacle detection (high priority) ---
                try:
                    tof_frame = tof.read_tof()
                    alert = obstacle_detector.check(tof_frame)
                    if alert:
                        msg = obstacle_detector.alert_message(alert)
                        audio.alert(msg)
                except Exception as exc:
                    logger.warning("ToF read error: %s", exc)

                # --- Visual localization ---
                try:
                    import cv2
                    gray = webcam.read_gray()
                    result = recognizer.recognize(gray)

                    if result.is_confident and result.waypoint:
                        current_id = result.waypoint.id
                        current_label = result.waypoint.label
                        logger.info("Localized: %s (conf=%.2f)", current_label, result.confidence)

                        # Start navigation on first confident localization
                        if not navigation_started:
                            instruction = navigator.start_navigation(current_label, args.destination)
                            navigation_started = True
                            if instruction:
                                audio.speak(instruction)
                            else:
                                audio.speak(f"No route found to {args.destination}.")

                        # Advance navigator when we reach a new waypoint
                        elif current_id != last_waypoint_id and navigator.state == NavigationState.NAVIGATING:
                            instruction = navigator.advance(current_id)
                            if instruction:
                                audio.speak(instruction)

                        last_waypoint_id = current_id

                        if navigator.state == NavigationState.ARRIVED:
                            audio.speak(f"You have arrived at {args.destination}.")
                            break

                except Exception as exc:
                    logger.warning("Localization error: %s", exc)

                # ~2 Hz navigation loop
                elapsed = time.monotonic() - loop_start
                sleep_time = max(0.0, 0.5 - elapsed)
                time.sleep(sleep_time)

    audio.shutdown()
    logger.info("Navigation session ended.")


if __name__ == "__main__":
    main()
