#!/usr/bin/env python3
"""
Guided navigation demo — voice destination input + planned-route guidance.

Flow:
  1. "Where do you want to go?" — listens via Vosk, matches a trained location
  2. Localize the current position, then plan a route (RouteGraph/Dijkstra)
     over trained WaypointEdges from here to the destination
  3. Follow the route step by step (GuidedNavigator) — each "forward" step
     is only taken if the ToF depth frame confirms it is actually clear;
     turns are announced directly from the edge's direction hint
  4. If no route exists (no trained edges, or starting position not
     recognized), fall back to pure reactive wall-following
  5. Trained "landmark" waypoints (e.g. doors) are announced when recognized
     close ahead
  6. Arrival is detected when the current view matches the destination

Usage:
    python scripts/navigate_voice.py --env my_home
    python scripts/navigate_voice.py --env my_home --destination kitchen   # skip voice
    python scripts/navigate_voice.py --env my_home --tof-mock
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
from nav_assistant.navigation.guided_navigator import GuidedNavigator, NavCommand
from nav_assistant.navigation.route_graph import RouteGraph
from nav_assistant.obstacle.detector import ObstacleDetector
from nav_assistant.perception.object_detector import ObjectClassifier
from nav_assistant.sensors.tof import ToFSensor
from nav_assistant.sensors.webcam import WebcamSensor
from nav_assistant.speech.recognizer import VoiceRecognizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("navigate_voice")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"
_RUNNING = True


def _handle_sigint(sig, frame) -> None:
    global _RUNNING
    _RUNNING = False
    print("\nNavigation stopped.")


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def localize_current_position(
    webcam: WebcamSensor,
    location_recognizer: PlaceRecognizer,
    attempts: int = 5,
    interval_s: float = 0.5,
) -> str | None:
    """
    Try a few quick reads to recognize which trained location the user is
    currently standing in. Returns the label, or None if no confident match
    is found within `attempts` tries (caller should fall back to reactive
    wall-following in that case).
    """
    for _ in range(attempts):
        gray = webcam.read_gray()
        result = location_recognizer.recognize(gray)
        if result.is_confident and result.waypoint is not None:
            return result.waypoint.label
        time.sleep(interval_s)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Guided navigation demo")
    parser.add_argument("--env", required=True)
    parser.add_argument("--destination", default=None,
                        help="Skip voice input and navigate directly to this location")
    parser.add_argument("--tof-mock", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    nav_cfg = cfg["navigation"]
    signal.signal(signal.SIGINT, _handle_sigint)

    audio = AudioGuidance(rate=cfg["audio"]["rate"], volume=cfg["audio"]["volume"])
    audio.initialize()

    webcam = WebcamSensor(
        device_name=cfg["webcam"].get("device_name"),
        device_index=cfg["webcam"]["device_index"],
        width=cfg["webcam"]["width"],
        height=cfg["webcam"]["height"],
        fps=cfg["webcam"]["fps"],
    )
    tof = ToFSensor(
        connection=cfg["tof"]["connection"],
        device_name=cfg["tof"].get("device_name", "unicam"),
        device_index=cfg["tof"]["device_index"],
        mock_mode=args.tof_mock,
    )
    # Tight emergency threshold — independent of the wall-following clear
    # distance, this only fires for something dangerously close (e.g. a
    # person stepping into the path), overriding the turn-by-turn guidance.
    emergency_detector = ObstacleDetector(
        alert_threshold_m=nav_cfg["emergency_threshold_m"],
        zone_fraction=cfg["obstacle"]["detection_zone_fraction"],
        cooldown_s=2.0,
    )
    object_classifier = ObjectClassifier(
        model_path=cfg["perception"]["yolo_model_path"],
        confidence_threshold=cfg["perception"]["confidence_threshold"],
    )
    if object_classifier.is_available:
        logger.info("YOLO object classification enabled for emergency alerts")

    with EnvironmentMap(args.env, environments_dir=cfg["data"]["environments_dir"]) as env:
        locations = env.list_waypoints(kind="location")
        if not locations:
            logger.error("No trained locations in '%s'. Run train.py first.", args.env)
            sys.exit(1)

        valid_labels = [w.label for w in locations]
        logger.info("Known locations: %s", valid_labels)

        location_recognizer = PlaceRecognizer(
            env,
            confidence_threshold=cfg["localization"]["confidence_threshold"],
            min_good_matches=cfg["localization"]["min_good_matches"],
            lowe_ratio=cfg["localization"]["match_ratio"],
        )
        location_recognizer.load(kind="location")

        landmark_recognizer = PlaceRecognizer(
            env,
            confidence_threshold=cfg["localization"]["confidence_threshold"],
            min_good_matches=cfg["localization"]["min_good_matches"],
            lowe_ratio=cfg["localization"]["match_ratio"],
        )
        landmark_recognizer.load(kind="landmark")

        navigator = GuidedNavigator(
            location_recognizer=location_recognizer,
            landmark_recognizer=landmark_recognizer,
            clear_distance_m=nav_cfg["clear_distance_m"],
            landmark_distance_m=nav_cfg["landmark_distance_m"],
        )

        with webcam, tof:
            destination = args.destination

            if destination is None:
                audio.speak("Where do you want to go?")
                voice = VoiceRecognizer(
                    cfg["speech"]["model_path"], cfg["speech"]["sample_rate"]
                )
                if voice.is_available:
                    destination = voice.listen_for_destination(valid_labels)
                else:
                    logger.error("Voice recognition unavailable (no Vosk model). "
                                 "Pass --destination instead.")

                if destination is None:
                    audio.speak("Sorry, I did not understand. Please try again.")
                    audio.shutdown()
                    return

            if destination not in valid_labels:
                audio.speak(f"{destination} is not a known location.")
                audio.shutdown()
                return

            # Try to identify the current location and plan a route using
            # any trained edges between it and the destination. If we can't
            # localize, or no route exists between the two, navigator.evaluate()
            # falls back to pure reactive wall-following automatically.
            current_label = localize_current_position(webcam, location_recognizer)
            if current_label is not None and current_label != destination:
                route_graph = RouteGraph(env)
                route_graph.build()
                try:
                    route = route_graph.plan(current_label, destination)
                except ValueError:
                    route = []
                if route:
                    navigator.set_route(route)
                    logger.info("Planned route: %s -> %s (%d step(s))",
                                current_label, destination, len(route))
                else:
                    logger.info("No trained route from '%s' to '%s' — using reactive navigation.",
                                current_label, destination)
            else:
                logger.info("Could not localize starting position — using reactive navigation.")

            audio.speak(f"Navigating to the {destination.replace('_', ' ')}.")

            last_message: str = ""
            last_spoken_time = 0.0
            repeat_interval = nav_cfg["repeat_interval_s"]

            while _RUNNING:
                loop_start = time.monotonic()

                try:
                    tof_frame = tof.read_tof()
                    gray = webcam.read_gray()
                except Exception as exc:
                    logger.warning("Sensor read error: %s", exc)
                    time.sleep(0.5)
                    continue

                # Emergency safety override — something dangerously close
                alert = emergency_detector.check(tof_frame)
                if alert:
                    message = emergency_detector.alert_message(alert)
                    if object_classifier.is_available:
                        bgr = webcam.read_bgr()
                        detection = object_classifier.classify(bgr)
                        if detection:
                            message = f"{detection.label.capitalize()} ahead, {alert.min_depth:.1f} metres."
                    audio.alert(message)

                result = navigator.evaluate(tof_frame, gray, destination)

                if result.command == NavCommand.ARRIVED:
                    audio.speak(result.message)
                    break

                now = time.monotonic()
                changed = result.message != last_message
                due_for_repeat = (now - last_spoken_time) >= repeat_interval
                if changed or due_for_repeat:
                    audio.speak(result.message)
                    last_message = result.message
                    last_spoken_time = now

                elapsed = time.monotonic() - loop_start
                time.sleep(max(0.0, 0.5 - elapsed))

    audio.shutdown()
    logger.info("Guided navigation ended.")


if __name__ == "__main__":
    main()
