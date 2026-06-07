#!/usr/bin/env python3
"""
Training mode — capture named locations for the awareness system.

Walk to each location you want the system to recognise, point the webcam
at a representative view, and run 'capture <label>'. The system stores
ORB visual descriptors and a ToF depth profile for each location.

Usage:
    python scripts/train.py --env my_home
    python scripts/train.py --env my_home --tof-mock

Commands:
    capture <label>    Capture current view as a named location
                       e.g. capture kitchen, capture hallway, capture office
    list               List all captured locations
    delete <label>     Delete a location
    quit               Save and exit

Note: 'edge' connections between locations are supported for future
navigation features but are not required for the awareness system.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from nav_assistant.mapping.environment import EnvironmentMap
from nav_assistant.mapping.recorder import WaypointRecorder
from nav_assistant.sensors.webcam import WebcamSensor
from nav_assistant.sensors.tof import ToFSensor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run_training_session(recorder: WaypointRecorder, env: EnvironmentMap) -> None:
    print("\nTraining session started. Type 'help' for commands.\n")

    while True:
        try:
            raw = input("train> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError as e:
            print(f"Parse error: {e}")
            continue

        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("Training complete. Environment saved.")
            break

        elif cmd == "help":
            print(__doc__)

        elif cmd == "capture":
            if len(parts) < 2:
                print("Usage: capture <label> [notes...]")
                continue
            label = parts[1]
            notes = " ".join(parts[2:]) if len(parts) > 2 else ""
            try:
                wp = recorder.capture_waypoint(label, notes=notes)
                print(f"  Captured: {wp.label} (id={wp.id[:8]})")
            except (ValueError, RuntimeError) as e:
                print(f"  Error: {e}")

        elif cmd == "edge":
            # edge <from> <to> <steps> <hint> <instruction>
            if len(parts) < 6:
                print('Usage: edge <from> <to> <steps> <hint> "<instruction>"')
                continue
            try:
                from_label, to_label = parts[1], parts[2]
                steps = int(parts[3])
                hint = parts[4]
                instruction = parts[5]
                edge = recorder.add_edge(from_label, to_label, steps, hint, instruction)
                print(f"  Edge added: {from_label} → {to_label} ({steps} steps)")
            except (ValueError, KeyError) as e:
                print(f"  Error: {e}")

        elif cmd == "list":
            waypoints = env.list_waypoints()
            if not waypoints:
                print("  No waypoints captured yet.")
            for wp in waypoints:
                print(f"  [{wp.id[:8]}] {wp.label:20s}  {wp.notes}")

        elif cmd == "delete":
            if len(parts) < 2:
                print("Usage: delete <label>")
                continue
            wp = env.get_waypoint_by_label(parts[1])
            if wp is None:
                print(f"  Waypoint '{parts[1]}' not found")
            else:
                env.delete_waypoint(wp.id)
                print(f"  Deleted: {parts[1]}")

        else:
            print(f"  Unknown command: {cmd!r}. Type 'help' for commands.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Training mode — capture waypoints")
    parser.add_argument("--env", required=True, help="Environment name (e.g. 'my_home')")
    parser.add_argument("--tof-mock", action="store_true", help="Use ToF mock mode")
    parser.add_argument("--webcam-index", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config()
    envs_dir = cfg["data"]["environments_dir"]

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
        frame_timeout_ms=cfg["tof"]["frame_timeout_ms"],
        mock_mode=args.tof_mock,
    )

    with EnvironmentMap(args.env, environments_dir=envs_dir) as env:
        with webcam, tof:
            recorder = WaypointRecorder(env, webcam, tof)
            run_training_session(recorder, env)


if __name__ == "__main__":
    main()
